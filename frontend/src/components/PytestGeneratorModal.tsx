import React, { useState } from 'react';
import { X, Check, Copy, Terminal, FileCode, Sparkles, CheckCircle2, ShieldCheck, Zap } from 'lucide-react';

interface PytestGeneratorModalProps {
  isOpen: boolean;
  onClose: () => void;
  candidateName: string;
  repoContext?: string;
}

export const PytestGeneratorModal: React.FC<PytestGeneratorModalProps> = ({
  isOpen,
  onClose,
  candidateName,
  repoContext = "https://github.com/jordan/task-manager"
}) => {
  if (!isOpen) return null;

  const [copied, setCopied] = useState<boolean>(false);

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

  const handleCopy = () => {
    navigator.clipboard.writeText(starterPytestCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fadeIn">
      <div className="w-full max-w-2xl bg-[#101112] border border-[#232426] rounded shadow-2xl overflow-hidden card-inner-glow flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="p-4 px-6 border-b border-[#1B1C1E] bg-[#0e0e0f] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-[#50d8e9]/10 border border-[#50d8e9]/30 flex items-center justify-center text-[#50d8e9]">
              <FileCode className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-heading font-bold text-base text-[#e5e2e3]">
                  Starter Pytest Suite Generator
                </h3>
                <span className="text-[10px] font-mono text-[#50d8e9] bg-[#50d8e9]/10 px-2 py-0.5 rounded border border-[#50d8e9]/20 font-bold">
                  +9% MATCH IMPACT
                </span>
              </div>
              <p className="text-[11px] font-mono text-[#9A9DA3]">
                Target: {repoContext.split('/').slice(-2).join('/')} • Candidate: {candidateName}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-[#9A9DA3] hover:text-[#e5e2e3] rounded hover:bg-[#1c1b1d] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-4 overflow-y-auto">
          {/* Action explanation banner */}
          <div className="bg-[#151617] border border-[#50d8e9]/20 rounded p-3.5 flex items-start gap-3">
            <Zap className="w-4 h-4 text-[#50d8e9] shrink-0 mt-0.5" />
            <div className="text-xs text-[#c6c5d8] leading-relaxed">
              <strong className="text-[#e5e2e3]">Removes Testing Refusal:</strong> Save this file as <code className="text-[#50d8e9] font-mono">tests/test_main.py</code> in your repository. Once committed, the AST code detective will register 5 unit tests with assertions and upgrade your role match from <strong className="text-[#ffb689]">54%</strong> to <strong className="text-[#50d8e9]">63%</strong>.
            </div>
          </div>

          {/* Code Box */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-[#9A9DA3] flex items-center gap-1.5">
                <Terminal className="w-3.5 h-3.5 text-[#50d8e9]" />
                <span>tests/test_main.py</span>
              </span>
              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 px-3 py-1 rounded bg-[#1c1b1d] border border-[#2a2a2b] hover:border-[#50d8e9] text-[11px] font-mono text-[#50d8e9] transition-all"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied to Clipboard!' : 'Copy Pytest Suite'}</span>
              </button>
            </div>

            <div className="bg-[#070708] border border-[#1B1C1E] rounded p-4 font-mono text-xs overflow-x-auto text-[#c6c5d8] leading-relaxed max-h-[380px]">
              <pre>{starterPytestCode}</pre>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-3 px-6 border-t border-[#1B1C1E] bg-[#0e0e0f] flex justify-between items-center text-xs font-mono">
          <span className="text-[#9A9DA3]">Run with: <code className="text-[#50d8e9]">pytest tests/ -v</code></span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded bg-[#1c1b1d] hover:bg-[#2a2a2b] text-[#e5e2e3] transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
