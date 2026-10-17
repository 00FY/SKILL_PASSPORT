import React, { useState } from 'react';
import { Check, Copy, Download, X } from 'lucide-react';

interface PytestGeneratorModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const PytestGeneratorModal: React.FC<PytestGeneratorModalProps> = ({ isOpen, onClose }) => {
  const [copied, setCopied] = useState(false);
  if (!isOpen) return null;

  const starterPytestCode = `import pytest
from fastapi.testclient import TestClient

# 1. Target candidate application instance
from app.main import app

client = TestClient(app)

def test_service_health():
    """Verify service health endpoint returns 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "ok"]

def test_create_task_route():
    """Test creating an item with required title and priority."""
    payload = {"title": "Implement Pytest Suite", "priority": 1}
    response = client.post("/tasks", json=payload)
    assert response.status_code in [200, 201]
    result = response.json()
    assert "id" in result or result.get("title") == payload["title"]

def test_reject_empty_task_payload():
    """Verify input validation handles empty payloads gracefully."""
    response = client.post("/tasks", json={"title": ""})
    assert response.status_code in [400, 422]

def test_fetch_pending_tasks():
    """Verify list route returns array of active items."""
    response = client.get("/tasks")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

@pytest.mark.parametrize("invalid_id", [-1, 999999, "abc"])
def test_handle_invalid_task_id(invalid_id):
    """Verify exception handler catches nonexistent task lookups."""
    response = client.get(f"/tasks/{invalid_id}")
    assert response.status_code in [404, 422]
`;

  const copy = () => {
    navigator.clipboard.writeText(starterPytestCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const download = () => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([starterPytestCode], { type: 'text/x-python' }));
    a.download = 'test_main.py';
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="flex max-h-[90vh] w-full max-w-2xl flex-col rounded-xl border border-white/10 bg-[#141516]">
        <div className="flex items-center justify-between border-b border-white/10 px-6 py-4">
          <h2 className="font-heading text-lg font-bold">Starter pytest file</h2>
          <button onClick={onClose} className="rounded p-1 text-zinc-400 hover:bg-white/10 hover:text-white" aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="space-y-3 overflow-y-auto px-6 py-4 text-sm">
          <p className="text-zinc-300">
            A generic FastAPI test file to start from. Rename the routes and payloads to match your app, save it as
            <code className="mx-1 text-indigo-300">tests/test_main.py</code>, commit, and run the audit again.
          </p>
          <pre className="overflow-auto rounded-lg bg-black/40 p-3 font-mono text-xs leading-relaxed text-zinc-200">{starterPytestCode}</pre>
        </div>
        <div className="flex justify-end gap-2 border-t border-white/10 px-6 py-3 text-sm">
          <button onClick={copy} className="flex items-center gap-2 rounded-lg border border-white/15 px-3 py-2 hover:bg-white/5">
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}{copied ? 'Copied' : 'Copy'}
          </button>
          <button onClick={download} className="flex items-center gap-2 rounded-lg bg-indigo-500 px-3 py-2 font-semibold text-white hover:bg-indigo-400">
            <Download className="h-4 w-4" />Download
          </button>
        </div>
      </div>
    </div>
  );
};
