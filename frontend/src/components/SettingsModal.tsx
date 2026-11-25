import { useCallback, useEffect, useState, type FormEvent } from "react";

import {
  AdminRequestError,
  adminIssueKey,
  adminListKeys,
  adminRevokeKey,
  adminUnlock,
  type ApiKeyRecord,
} from "../api";

const TOKEN_KEY = "tableflow.admin.token";

function readToken(): string {
  try {
    // 口令只进 sessionStorage：关掉标签页即失效，不进 localStorage
    return sessionStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

function writeToken(value: string | null): void {
  try {
    if (value) {
      sessionStorage.setItem(TOKEN_KEY, value);
    } else {
      sessionStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    /* 隐私模式下 sessionStorage 可能不可用，退化为仅内存保存 */
  }
}

function describeError(error: unknown): string {
  if (error instanceof AdminRequestError) {
    if (error.status === 503) {
      return "该实例未配置管理口令（TABLEFLOW_ADMIN_TOKEN），设置页不可用";
    }
    if (error.status === 401) {
      return "管理口令错误";
    }
    if (error.status === 0) {
      return "请求超时，请重试";
    }
    return error.message;
  }
  return error instanceof Error ? error.message : String(error);
}

function formatTime(value: string): string {
  return value.replace("T", " ").slice(0, 19);
}

export function SettingsModal({ onClose }: { onClose: () => void }) {
  const [token, setToken] = useState<string>(() => readToken());
  const [draft, setDraft] = useState("");
  const [unlocked, setUnlocked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [keys, setKeys] = useState<ApiKeyRecord[] | null>(null);
  const [plaintext, setPlaintext] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [label, setLabel] = useState("");
  const [note, setNote] = useState("");

  // 打开时用已存口令自动恢复；失效则清掉，不让用户看到假解锁
  useEffect(() => {
    const saved = readToken();
    if (!saved) {
      return;
    }
    let cancelled = false;
    adminListKeys(saved)
      .then((list) => {
        if (!cancelled) {
          setKeys(list);
          setUnlocked(true);
        }
      })
      .catch(() => {
        if (!cancelled) {
          writeToken(null);
          setToken("");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const unlock = async (event: FormEvent) => {
    event.preventDefault();
    const value = draft.trim();
    if (!value) {
      setError("请输入管理口令");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await adminUnlock(value);
      const list = await adminListKeys(value);
      writeToken(value);
      setToken(value);
      setKeys(list);
      setUnlocked(true);
      setDraft("");
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  };

  const refresh = useCallback(async () => {
    setKeys(await adminListKeys(token));
  }, [token]);

  const issue = async (event: FormEvent) => {
    event.preventDefault();
    if (!label.trim()) {
      setError("请填写 label（调用者身份）");
      return;
    }
    setBusy(true);
    setError(null);
    setCopied(false);
    try {
      const result = await adminIssueKey(token, label.trim(), note);
      setPlaintext(result.plaintext);
      setLabel("");
      setNote("");
      await refresh();
    } catch (err) {
      if (err instanceof AdminRequestError && err.status === 401) {
        writeToken(null);
        setToken("");
        setUnlocked(false);
      }
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (record: ApiKeyRecord) => {
    if (
      !window.confirm(`吊销 ${record.id}（${record.label}）？吊销后立即失效，且不可恢复。`)
    ) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await adminRevokeKey(token, record.id);
      await refresh();
    } catch (err) {
      if (err instanceof AdminRequestError && err.status === 401) {
        writeToken(null);
        setToken("");
        setUnlocked(false);
      }
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  };

  const copyPlaintext = async () => {
    if (!plaintext) {
      return;
    }
    try {
      await navigator.clipboard.writeText(plaintext);
      setCopied(true);
    } catch {
      setCopied(false);
      setError("复制失败，请手工选中复制");
    }
  };

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal modal-wide settings-modal"
        role="dialog"
        aria-modal="true"
        aria-label="设置"
        onClick={(event) => event.stopPropagation()}
      >
        <header>
          <h2>设置</h2>
          <button type="button" onClick={onClose}>
            关闭
          </button>
        </header>

        {unlocked ? (
          <>
            <section className="settings-section">
              <h3>签发 API Key</h3>
              <p className="settings-hint">
                key 是调用者身份，明文只在签发的这一刻显示一次；配到对应项目的
                <code>TF_API_KEY</code> 环境变量即可。
              </p>
              <form className="settings-form" onSubmit={issue}>
                <label>
                  <span>label（调用者身份）</span>
                  <input
                    value={label}
                    onChange={(event) => setLabel(event.target.value)}
                    placeholder="demo-cnc-agent"
                    maxLength={64}
                    autoFocus
                  />
                </label>
                <label>
                  <span>备注（可省略）</span>
                  <input
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                    placeholder="demo-cnc 项目 Agent"
                    maxLength={200}
                  />
                </label>
                <button type="submit" className="settings-primary" disabled={busy}>
                  {busy ? "处理中" : "签发"}
                </button>
              </form>
              {plaintext ? (
                <div className="secret-reveal" role="status">
                  <div className="secret-reveal-head">新 key（只显示这一次）</div>
                  <code className="secret-reveal-value">{plaintext}</code>
                  <button type="button" onClick={copyPlaintext}>
                    {copied ? "已复制" : "复制"}
                  </button>
                </div>
              ) : null}
            </section>

            <section className="settings-section">
              <h3>已有 Key</h3>
              {keys === null ? (
                <p className="settings-hint">加载中…</p>
              ) : keys.length === 0 ? (
                <p className="settings-hint">还没有任何 key</p>
              ) : (
                <table className="key-table">
                  <thead>
                    <tr>
                      <th>key_id</th>
                      <th>label</th>
                      <th>状态</th>
                      <th>签发时间</th>
                      <th>备注</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {keys.map((record) => (
                      <tr key={record.id} className={record.revoked_at ? "is-revoked" : undefined}>
                        <td>
                          <code>{record.id}</code>
                        </td>
                        <td>{record.label}</td>
                        <td>
                          {record.revoked_at ? (
                            <span className="key-status is-revoked">
                              已吊销 {formatTime(record.revoked_at)}
                            </span>
                          ) : (
                            <span className="key-status">有效</span>
                          )}
                        </td>
                        <td>{formatTime(record.created_at)}</td>
                        <td>{record.note ?? ""}</td>
                        <td>
                          {record.revoked_at ? null : (
                            <button
                              type="button"
                              className="key-revoke"
                              onClick={() => revoke(record)}
                              disabled={busy}
                            >
                              吊销
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>
          </>
        ) : (
          <section className="settings-section">
            <p className="settings-hint">
              设置页需要管理口令。口令由部署侧环境变量
              <code>TABLEFLOW_ADMIN_TOKEN</code> 提供。
            </p>
            <form className="settings-form" onSubmit={unlock}>
              <label>
                <span>管理口令</span>
                <input
                  type="password"
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  autoFocus
                  autoComplete="off"
                />
              </label>
              <button type="submit" className="settings-primary" disabled={busy}>
                {busy ? "校验中" : "进入设置"}
              </button>
            </form>
          </section>
        )}

        {error ? (
          <p className="settings-error" role="alert">
            {error}
          </p>
        ) : null}
      </div>
    </div>
  );
}
