import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react";
import { api } from "./api";
import { CASE_PAGE_SIZE } from "./api/cases";
import CaseFormModal from "./CaseFormModal";
import CaseList from "./CaseList";
import CasePreviewModal from "./CasePreviewModal";
import {
  IDENTIFIER_REQUIRED,
  emptyForm,
  joinEmails,
  splitEmails,
} from "./caseConstants";
import { copyText } from "./copyText";
import useConfirm from "./useConfirm";

const FeedbackWorkspace = forwardRef(function FeedbackWorkspace(
  { onNotice, onRefreshLogs },
  ref
) {
  const previewUrlRef = useRef("");
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [rows, setRows] = useState([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const pageRef = useRef(1);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [modal, setModal] = useState(false);
  const [mode, setMode] = useState("view");
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [confirm, confirmDialog] = useConfirm();
  const [pendingFiles, setPendingFiles] = useState([]);
  const [files, setFiles] = useState([]);
  const [preview, setPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [formError, setFormError] = useState("");
  const [copiedField, setCopiedField] = useState("");
  const [statusBusy, setStatusBusy] = useState(null);

  const releasePreviewUrl = useCallback(() => {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = "";
    }
  }, []);

  const clearPreview = useCallback(() => {
    releasePreviewUrl();
    setPreview(null);
    setPreviewLoading(false);
  }, [releasePreviewUrl]);

  useEffect(() => () => releasePreviewUrl(), [releasePreviewUrl]);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(query), 250);
    return () => clearTimeout(timer);
  }, [query]);

  const load = useCallback(
    async (pageToLoad) => {
      const target = pageToLoad ?? pageRef.current;
      setLoading(true);
      try {
        const result = await api.listCases(debounced, target, CASE_PAGE_SIZE);
        const meta = result.pagination || {
          page: target,
          total: 0,
          totalPages: 1,
          pageSize: CASE_PAGE_SIZE,
        };
        setRows(result.data || []);
        pageRef.current = meta.page || target;
        setPage(meta.page || target);
        setTotal(meta.total || 0);
        setTotalPages(meta.totalPages || 1);
      } catch (error) {
        onNotice?.({ type: "error", text: error.message });
      } finally {
        setLoading(false);
      }
    },
    [debounced, onNotice]
  );

  useEffect(() => {
    load(1);
  }, [load]);

  const showLocalPreview = useCallback(
    (file) => {
      releasePreviewUrl();
      if (!String(file.type || "").startsWith("image/")) {
        setPreview(null);
        onNotice?.({ type: "error", text: "This file can be previewed after the case is saved." });
        return;
      }
      const url = URL.createObjectURL(file);
      previewUrlRef.current = url;
      setPreview({
        kind: "image",
        url,
        file: { id: file.name, originalName: file.name },
      });
    },
    [onNotice, releasePreviewUrl]
  );

  const openSavedPreview = useCallback(
    async (caseId, file) => {
      setPreviewLoading(true);
      try {
        const result = await api.previewCaseFile(caseId, file.id);
        releasePreviewUrl();
        setPreview(result.data);
      } catch (error) {
        setPreview(null);
        onNotice?.({ type: "error", text: error.message });
      } finally {
        setPreviewLoading(false);
      }
    },
    [onNotice, releasePreviewUrl]
  );

  const uploadFiles = useCallback(
    async (caseId, chosen) => {
      if (!chosen.length) {
        return;
      }
      setUploading(true);
      try {
        for (const file of chosen) {
          await api.uploadCaseFile(caseId, file);
        }
        const result = await api.getCase(caseId);
        setEditing(result.data);
        setFiles(result.data.files || []);
        await load();
        await onRefreshLogs?.();
      } catch (error) {
        onNotice?.({ type: "error", text: error.message });
      } finally {
        setUploading(false);
      }
    },
    [load, onNotice, onRefreshLogs]
  );

  const onPendingFromClipboard = useCallback(
    (images) => {
      if (editing?.id) {
        uploadFiles(editing.id, images);
        return;
      }
      setPendingFiles((current) => [...current, ...images]);
      showLocalPreview(images[images.length - 1]);
    },
    [editing, showLocalPreview, uploadFiles]
  );

  const changeStatus = async (row, status) => {
    if (!row?.id || !status || status === row.status) {
      return;
    }
    setStatusBusy(row.id);
    try {
      const result = await api.setCaseStatus(row.id, status);
      const next = result.data?.status || status;
      setRows((current) =>
        current.map((item) => (item.id === row.id ? { ...item, status: next } : item))
      );
      if (editing?.id === row.id) {
        setEditing((current) => (current ? { ...current, status: next } : current));
        setForm((current) => ({ ...current, status: next }));
      }
      onNotice?.({ type: "success", text: result.message || "Status updated" });
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setStatusBusy(null);
    }
  };

  const openNew = () => {
    setEditing(null);
    setForm(emptyForm);
    setPendingFiles([]);
    setFiles([]);
    setFormError("");
    clearPreview();
    setMode("new");
    setModal(true);
  };

  useImperativeHandle(ref, () => ({ openNew }));

  const applyCase = (data) => {
    setEditing(data);
    setForm({
      bookingOrderId: data.bookingOrderId || "",
      shipmentNumber: data.shipmentNumber || "",
      email: data.email || "",
      description: data.description || "",
      status: data.status || "pending_review",
    });
    setPendingFiles([]);
    setFiles(data.files || []);
    setFormError("");
    setCopiedField("");
    clearPreview();
  };

  const openCase = async (row, nextMode) => {
    try {
      const result = await api.getCase(row.id);
      applyCase(result.data);
      setMode(nextMode);
      setModal(true);
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    }
  };

  const copyPreviewValue = async (field, value) => {
    const text = String(value || "").trim();
    if (!text) {
      return;
    }
    try {
      await copyText(text);
      setCopiedField(field);
      onNotice?.({ type: "success", text: "Copied" });
    } catch {
      onNotice?.({ type: "error", text: "Could not copy to the clipboard." });
    }
  };

  const closeModal = () => {
    if (!saving && !uploading) {
      clearPreview();
      setCopiedField("");
      setMode("view");
      setModal(false);
    }
  };

  const save = async (event) => {
    event.preventDefault();
    const bookingOrderId = form.bookingOrderId.trim();
    const shipmentNumber = form.shipmentNumber.trim();
    if (!bookingOrderId && !shipmentNumber) {
      setFormError(IDENTIFIER_REQUIRED);
      return;
    }
    setFormError("");
    const payload = {
      bookingOrderId,
      shipmentNumber,
      email: joinEmails(splitEmails(form.email)),
      description: form.description.trim(),
      status: form.status,
    };
    setSaving(true);
    try {
      let caseId = editing?.id;
      if (editing) {
        const result = await api.updateCase(editing.id, payload);
        onNotice?.({ type: "success", text: result.message });
        setEditing(result.data);
        setFiles(result.data.files || []);
      } else {
        const result = await api.createCase(payload);
        caseId = result.data.id;
        for (const file of pendingFiles) {
          await api.uploadCaseFile(caseId, file);
        }
        onNotice?.({ type: "success", text: result.message });
        clearPreview();
        setModal(false);
      }
      await load(editing ? pageRef.current : 1);
      await onRefreshLogs?.();
    } catch (error) {
      setFormError(error.message);
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setSaving(false);
      setPendingFiles([]);
    }
  };

  const remove = async (row) => {
    const ok = await confirm({
      title: "Delete case",
      message: "Delete this case?",
    });
    if (!ok) {
      return;
    }
    try {
      const result = await api.deleteCase(row.id);
      onNotice?.({ type: "success", text: result.message });
      if (editing?.id === row.id) {
        clearPreview();
        setModal(false);
      }
      const nextPage = rows.length === 1 && page > 1 ? page - 1 : page;
      await load(nextPage);
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    }
  };

  const addPendingFiles = (event) => {
    const chosen = Array.from(event.target.files || []);
    if (chosen.length) {
      setPendingFiles((current) => [...current, ...chosen]);
    }
    event.target.value = "";
  };

  const attachExisting = async (event) => {
    const chosen = Array.from(event.target.files || []);
    event.target.value = "";
    if (!chosen.length || !editing?.id) {
      return;
    }
    await uploadFiles(editing.id, chosen);
  };

  const removeFile = async (file) => {
    if (!editing?.id) {
      setPendingFiles((current) => current.filter((item) => item !== file));
      if (preview?.file?.originalName === file.name && preview?.url?.startsWith("blob:")) {
        clearPreview();
      }
      return;
    }
    try {
      await api.deleteCaseFile(editing.id, file.id);
      setFiles((current) => current.filter((item) => item.id !== file.id));
      if (preview?.file?.id === file.id) {
        clearPreview();
      }
      await load();
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    }
  };

  return (
    <>
      <CaseList
        query={query}
        onQueryChange={setQuery}
        total={total}
        loading={loading}
        rows={rows}
        page={page}
        totalPages={totalPages}
        statusBusy={statusBusy}
        saving={saving}
        onOpenCase={openCase}
        onChangeStatus={changeStatus}
        onLoadPage={load}
      />
      {modal && mode === "view" ? (
        <CasePreviewModal
          editing={editing}
          files={files}
          preview={preview}
          previewLoading={previewLoading}
          copiedField={copiedField}
          busy={saving || uploading}
          onClose={closeModal}
          onEdit={() => setMode("edit")}
          onCopy={copyPreviewValue}
          onOpenPreview={openSavedPreview}
          onClearPreview={clearPreview}
        />
      ) : null}
      {modal && mode !== "view" ? (
        <CaseFormModal
          mode={mode}
          editing={editing}
          form={form}
          setForm={setForm}
          formError={formError}
          saving={saving}
          uploading={uploading}
          statusBusy={statusBusy}
          pendingFiles={pendingFiles}
          files={files}
          preview={preview}
          previewLoading={previewLoading}
          onClose={closeModal}
          onSave={save}
          onDelete={remove}
          onChangeStatus={changeStatus}
          onAddPendingFiles={addPendingFiles}
          onAttachExisting={attachExisting}
          onRemoveFile={removeFile}
          onShowLocalPreview={showLocalPreview}
          onOpenSavedPreview={openSavedPreview}
          onClearPreview={clearPreview}
          onPendingFromClipboard={onPendingFromClipboard}
        />
      ) : null}
      {confirmDialog}
    </>
  );
});

export default FeedbackWorkspace;
