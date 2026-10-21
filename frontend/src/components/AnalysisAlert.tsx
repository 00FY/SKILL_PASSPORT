import React, { useEffect, useRef } from 'react';
import { AlertTriangle } from 'lucide-react';

export interface AnalysisNotice {
  title: string;
  messages: string[];
}

/** A top-layer dialog stays visible even when the upload form is scrolled. */
export const AnalysisAlert: React.FC<{
  notice: AnalysisNotice | null;
  onClose: () => void;
}> = ({ notice, onClose }) => {
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (notice && !dialog.current?.open) dialog.current?.showModal();
    if (!notice && dialog.current?.open) dialog.current.close();
  }, [notice]);

  return (
    <dialog
      ref={dialog}
      role="alertdialog"
      aria-labelledby="analysis-alert-title"
      aria-describedby="analysis-alert-description"
      onCancel={event => { event.preventDefault(); onClose(); }}
      className="m-auto w-[calc(100%_-_2rem)] max-w-lg rounded-xl border border-amber-400/40 bg-[#17181a] p-6 text-zinc-100 shadow-2xl backdrop:bg-black/75"
    >
      {notice && <>
        <div className="mb-3 flex items-center gap-3">
          <AlertTriangle className="h-6 w-6 shrink-0 text-amber-300" />
          <h2 id="analysis-alert-title" className="text-lg font-semibold">{notice.title}</h2>
        </div>
        <div id="analysis-alert-description" className="max-h-[55vh] space-y-3 overflow-y-auto break-words text-sm leading-relaxed text-zinc-300">
          {notice.messages.map((message, index) => <p key={index}>{message}</p>)}
        </div>
        <div className="mt-5 flex justify-end">
          <button autoFocus onClick={onClose} className="rounded-lg bg-indigo-500 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-400">
            Understood
          </button>
        </div>
      </>}
    </dialog>
  );
};
