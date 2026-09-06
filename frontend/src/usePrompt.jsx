import { useCallback, useState } from "react";
import PromptDialog from "./PromptDialog";

export default function usePrompt() {
  const [request, setRequest] = useState(null);

  const prompt = useCallback((options) => {
    return new Promise((resolve) => {
      setRequest({
        title: options.title || "Rename",
        message: options.message,
        label: options.label || "Name",
        defaultValue: options.defaultValue || "",
        confirmLabel: options.confirmLabel || "Save",
        cancelLabel: options.cancelLabel || "Cancel",
        resolve,
      });
    });
  }, []);

  const close = (value) => {
    request?.resolve(value);
    setRequest(null);
  };

  const dialog = request ? (
    <PromptDialog
      title={request.title}
      message={request.message}
      label={request.label}
      defaultValue={request.defaultValue}
      confirmLabel={request.confirmLabel}
      cancelLabel={request.cancelLabel}
      onCancel={() => close(null)}
      onConfirm={(value) => close(value)}
    />
  ) : null;

  return [prompt, dialog];
}
