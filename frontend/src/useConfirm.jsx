import { useCallback, useState } from "react";
import ConfirmDialog from "./ConfirmDialog";

export default function useConfirm() {
  const [request, setRequest] = useState(null);

  const confirm = useCallback((options) => {
    return new Promise((resolve) => {
      setRequest({
        title: options.title || "Please confirm",
        message: options.message,
        confirmLabel: options.confirmLabel || "Delete",
        cancelLabel: options.cancelLabel || "Cancel",
        danger: options.danger !== false,
        resolve,
      });
    });
  }, []);

  const close = (ok) => {
    request?.resolve(ok);
    setRequest(null);
  };

  const dialog = request ? (
    <ConfirmDialog
      title={request.title}
      message={request.message}
      confirmLabel={request.confirmLabel}
      cancelLabel={request.cancelLabel}
      danger={request.danger}
      onCancel={() => close(false)}
      onConfirm={() => close(true)}
    />
  ) : null;

  return [confirm, dialog];
}
