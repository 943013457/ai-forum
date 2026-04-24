import { useEffect, useState } from "react";
import {
  getEngineStatus, stopEngine, generateUsers, getEngineLogs,
  getAdminStats, getBans, createBan, removeBan, getAltAccounts,
  getAnnouncements, createAnnouncement, deleteAnnouncement,
} from "../api";
import type { EngineStatus, EngineLog, AdminStats, Ban, AltAccount, AnnouncementItem } from "../api";
import { Activity, Users, FileText, MessageCircle, Zap, Shield, UserX, Loader2, RefreshCw, Square, Bot } from "lucide-react";

export default function AdminPage() {
  const [status, setStatus] = useState<EngineStatus | null>(null);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [logs, setLogs] = useState<EngineLog[]>([]);
  const [bans, setBans] = useState<Ban[]>([]);
  const [alts, setAlts] = useState<AltAccount[]>([]);
  const [announcements, setAnnouncements] = useState<AnnouncementItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"overview" | "logs" | "bans" | "alts" | "announcements">("overview");

  // Ban form
  const [banUserId, setBanUserId] = useState("");
  const [banReason, setBanReason] = useState("");
  const [banDuration, setBanDuration] = useState("24h");

  // Announcement form
  const [annTitle, setAnnTitle] = useState("");
  const [annContent, setAnnContent] = useState("");
  const [annReward, setAnnReward] = useState(0);
  const [annDays, setAnnDays] = useState(7);

  const refresh = async () => {
    setLoading(true);
    const [s, st, l, b, a, ann] = await Promise.all([
      getEngineStatus().catch(() => null),
      getAdminStats().catch(() => null),
      getEngineLogs(30).catch(() => []),
      getBans().catch(() => []),
      getAltAccounts().catch(() => []),
      getAnnouncements().catch(() => []),
    ]);
    setStatus(s);
    setStats(st);
    setLogs(l as EngineLog[]);
    setBans(b as Ban[]);
    setAlts(a as AltAccount[]);
    setAnnouncements(ann as AnnouncementItem[]);
    setLoading(false);
  };

  useEffect(() => { refresh(); }, []);

  const handleStop = async () => {
    await stopEngine();
    await refresh();
  };

  const handleGenerate = async () => {
    await generateUsers(50);
    await refresh();
  };

  const handleCreateBan = async () => {
    if (!banUserId || !banReason) return;
    await createBan({ user_id: Number(banUserId), reason: banReason, duration: banDuration });
    setBanUserId(""); setBanReason("");
    const b = await getBans().catch(() => []);
    setBans(b as Ban[]);
  };

  const handleRemoveBan = async (id: number) => {
    await removeBan(id);
    setBans(bans.filter((b) => b.id !== id));
  };

  const [annLoading, setAnnLoading] = useState(false);
  const [annError, setAnnError] = useState("");

  const handleCreateAnnouncement = async () => {
    if (!annTitle || !annContent) {
      setAnnError("请填写标题和内容");
      return;
    }
    setAnnLoading(true);
    setAnnError("");
    try {
      const now = new Date();
      const end = new Date(now.getTime() + annDays * 24 * 60 * 60 * 1000);
      await createAnnouncement({
        title: annTitle,
        content: annContent,
        reward_credits: annReward,
        start_time: now.toISOString(),
        end_time: end.toISOString(),
      });
      setAnnTitle(""); setAnnContent(""); setAnnReward(0); setAnnDays(7);
      const ann = await getAnnouncements().catch(() => []);
      setAnnouncements(ann as AnnouncementItem[]);
    } catch (e: any) {
      setAnnError(`发布失败: ${e.message || e}`);
    } finally {
      setAnnLoading(false);
    }
  };

  const handleDeleteAnnouncement = async (id: number) => {
    await deleteAnnouncement(id);
    setAnnouncements(announcements.filter((a) => a.id !== id));
  };

  if (loading) return <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 animate-spin text-primary-500" /></div>;

  const TABS = [
    { key: "overview" as const, label: "概览" },
    { key: "announcements" as const, label: "公告" },
    { key: "logs" as const, label: "引擎日志" },
    { key: "bans" as const, label: "禁言" },
    { key: "alts" as const, label: "小号" },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2 text-dark-text">
          <Shield className="w-6 h-6 text-primary-500" /> 管理面板
        </h1>
        <button onClick={refresh} className="flex items-center gap-1 text-sm text-dark-muted hover:text-primary-500">
          <RefreshCw className="w-4 h-4" /> 刷新
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-dark-card border border-dark-border rounded-lg p-0.5 mb-6 w-fit">
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-4 py-1.5 rounded-md text-sm transition-colors ${
              tab === key ? "bg-primary-500 text-white font-medium" : "text-dark-muted"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="space-y-6">
          {/* 引擎状态 */}
          <div className="bg-dark-card rounded-xl border border-dark-border p-6">
            <h2 className="font-semibold text-dark-text flex items-center gap-2 mb-4">
              <Activity className="w-5 h-5 text-primary-500" /> 世界引擎
            </h2>
            {status && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center">
                  <div className={`text-lg font-bold ${status.running ? "text-green-600" : "text-red-500"}`}>
                    {status.running ? "运行中" : "已停止"}
                  </div>
                  <div className="text-xs text-dark-muted">状态</div>
                </div>
                <div className="text-center">
                  <div className="text-lg font-bold text-dark-text">{status.tick_number}</div>
                  <div className="text-xs text-dark-muted">世界刻</div>
                </div>
                <div className="text-center">
                  <div className="text-lg font-bold text-dark-text">{status.llm_calls_this_hour}</div>
                  <div className="text-xs text-dark-muted">本刻 LLM 调用</div>
                </div>
                <div className="text-center">
                  <div className="flex gap-2 justify-center">
                    <button onClick={handleStop} disabled={!status.running}
                      className="flex items-center gap-1 px-3 py-1 bg-primary-50 text-primary-500 rounded-lg text-sm hover:bg-primary-100 disabled:opacity-40">
                      <Square className="w-3 h-3" /> 停止
                    </button>
                    <button onClick={handleGenerate}
                      className="flex items-center gap-1 px-3 py-1 bg-dark-surface text-primary-500 rounded-lg text-sm hover:bg-dark-hover border border-dark-border">
                      <Bot className="w-3 h-3" /> +50用户
                    </button>
                  </div>
                  <div className="text-xs text-dark-muted mt-1">操作</div>
                </div>
              </div>
            )}
          </div>

          {/* 统计概览 */}
          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {[
                { icon: Users, label: "总用户", value: stats.total_users, color: "text-blue-400" },
                { icon: FileText, label: "总帖子", value: stats.total_posts, color: "text-green-400" },
                { icon: MessageCircle, label: "总评论", value: stats.total_comments, color: "text-purple-400" },
                { icon: FileText, label: "今日帖子", value: stats.today_posts, color: "text-amber-400" },
                { icon: MessageCircle, label: "今日评论", value: stats.today_comments, color: "text-pink-400" },
                { icon: Zap, label: "进行中约架", value: stats.active_debates, color: "text-primary-500" },
              ].map(({ icon: Icon, label, value, color }) => (
                <div key={label} className="bg-dark-card rounded-xl border border-dark-border p-4 flex items-center gap-3">
                  <Icon className={`w-8 h-8 ${color}`} />
                  <div>
                    <div className="text-xl font-bold text-dark-text">{value}</div>
                    <div className="text-xs text-dark-muted">{label}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === "logs" && (
        <div className="bg-dark-card rounded-xl border border-dark-border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-dark-surface text-dark-muted text-xs">
              <tr>
                <th className="px-4 py-2 text-left">Tick</th>
                <th className="px-4 py-2 text-right">活跃</th>
                <th className="px-4 py-2 text-right">帖子</th>
                <th className="px-4 py-2 text-right">评论</th>
                <th className="px-4 py-2 text-right">点赞</th>
                <th className="px-4 py-2 text-right">LLM</th>
                <th className="px-4 py-2 text-right">时间</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-border">
              {logs.map((l) => (
                <tr key={l.id} className="hover:bg-dark-hover">
                  <td className="px-4 py-2 font-mono">#{l.tick_number}</td>
                  <td className="px-4 py-2 text-right">{l.active_users_count}</td>
                  <td className="px-4 py-2 text-right text-green-600">{l.posts_generated}</td>
                  <td className="px-4 py-2 text-right text-blue-600">{l.comments_generated}</td>
                  <td className="px-4 py-2 text-right text-pink-600">{l.likes_generated}</td>
                  <td className="px-4 py-2 text-right text-amber-600">{l.llm_calls}</td>
                  <td className="px-4 py-2 text-right text-dark-muted text-xs">{new Date(l.timestamp).toLocaleString("zh-CN")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {logs.length === 0 && <p className="text-center text-dark-muted py-8 text-sm">暂无日志</p>}
        </div>
      )}

      {tab === "announcements" && (
        <div className="space-y-4">
          {/* 创建公告 */}
          <div className="bg-dark-card rounded-xl border border-dark-border p-5">
            <h3 className="font-semibold text-dark-text mb-3">发布新公告</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <input value={annTitle} onChange={(e) => setAnnTitle(e.target.value)}
                placeholder="公告标题" className="bg-dark-surface border border-dark-border rounded-lg px-3 py-2 text-sm text-dark-text" />
              <div className="flex gap-2">
                <input type="number" value={annReward} onChange={(e) => setAnnReward(Number(e.target.value))}
                  placeholder="奖励积分" min={0} max={300}
                  className="bg-dark-surface border border-dark-border rounded-lg px-3 py-2 text-sm text-dark-text w-28" />
                <select value={annDays} onChange={(e) => setAnnDays(Number(e.target.value))}
                  className="bg-dark-surface border border-dark-border rounded-lg px-3 py-2 text-sm text-dark-text">
                  <option value={1}>1天</option>
                  <option value={3}>3天</option>
                  <option value={7}>7天</option>
                  <option value={14}>14天</option>
                  <option value={30}>30天</option>
                </select>
              </div>
            </div>
            <textarea value={annContent} onChange={(e) => setAnnContent(e.target.value)}
              placeholder="公告内容（描述活动规则、话题引导等）"
              className="mt-2 w-full bg-dark-surface border border-dark-border rounded-lg px-3 py-2 text-sm text-dark-text h-20 resize-none" />
            <div className="flex justify-between items-center mt-3">
              <div>
                <span className="text-xs text-dark-muted">
                  参与率: {annReward === 0 ? "5%" : `${Math.round(5 + (Math.min(annReward, 300) / 300) * 45)}%`}
                  （积分越高参与越多，最高50%）
                </span>
                {annError && <p className="text-xs text-primary-500 mt-1">{annError}</p>}
              </div>
              <button type="button" onClick={handleCreateAnnouncement} disabled={annLoading}
                className="px-4 py-1.5 bg-primary-500 text-white rounded-lg text-sm hover:bg-primary-400 disabled:opacity-50">
                {annLoading ? "发布中..." : "发布"}
              </button>
            </div>
          </div>

          {/* 公告列表 */}
          <div className="bg-dark-card rounded-xl border border-dark-border divide-y divide-dark-border">
            {announcements.length === 0 ? (
              <p className="text-center text-dark-muted py-8 text-sm">暂无公告</p>
            ) : (
              announcements.map((a) => (
                <div key={a.id} className="px-5 py-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="font-medium">{a.title}</span>
                      {a.reward_credits > 0 && (
                        <span className="text-xs bg-amber-900/30 text-amber-400 px-2 py-0.5 rounded-full ml-2">
                          🎁 {a.reward_credits}积分
                        </span>
                      )}
                      <span className={`text-xs ml-2 ${a.is_active ? "text-green-400" : "text-dark-muted"}`}>
                        {a.is_active ? "进行中" : "已结束"}
                      </span>
                    </div>
                    <button onClick={() => handleDeleteAnnouncement(a.id)}
                      className="text-sm text-primary-500 hover:text-primary-400">删除</button>
                  </div>
                  <p className="text-sm text-dark-muted mt-1">{a.content}</p>
                  <div className="text-xs text-dark-muted mt-1">
                    {new Date(a.start_time).toLocaleDateString("zh-CN")} ~ {new Date(a.end_time).toLocaleDateString("zh-CN")}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {tab === "bans" && (
        <div className="space-y-4">
          {/* 禁言表单 */}
          <div className="bg-dark-card rounded-xl border border-dark-border p-5">
            <h3 className="font-semibold text-dark-text mb-3">禁言用户</h3>
            <div className="flex gap-2 items-center">
              <input value={banUserId} onChange={(e) => setBanUserId(e.target.value)}
                placeholder="用户 ID" className="bg-dark-surface border border-dark-border rounded-lg px-3 py-2 text-sm text-dark-text w-24" />
              <input value={banReason} onChange={(e) => setBanReason(e.target.value)}
                placeholder="禁言理由" className="bg-dark-surface border border-dark-border rounded-lg px-3 py-2 text-sm text-dark-text flex-1" />
              <select value={banDuration} onChange={(e) => setBanDuration(e.target.value)}
                className="bg-dark-surface border border-dark-border rounded-lg px-3 py-2 text-sm text-dark-text">
                <option value="24h">24小时</option>
                <option value="3d">3天</option>
                <option value="7d">7天</option>
                <option value="30d">30天</option>
                <option value="permanent">永久</option>
              </select>
              <button onClick={handleCreateBan}
                className="px-4 py-2 bg-primary-500 text-white rounded-lg text-sm hover:bg-primary-400">禁言</button>
            </div>
          </div>

          {/* 禁言列表 */}
          <div className="bg-dark-card rounded-xl border border-dark-border divide-y divide-dark-border">
            {bans.length === 0 ? (
              <p className="text-center text-dark-muted py-8 text-sm">暂无禁言</p>
            ) : (
              bans.map((b) => (
                <div key={b.id} className="flex items-center justify-between px-5 py-3">
                  <div>
                    <span className="font-medium">用户 #{b.user_id}</span>
                    <span className="text-sm text-dark-muted ml-2">{b.reason}</span>
                    <span className="text-xs text-dark-muted ml-2">
                      {b.banned_until ? `到 ${new Date(b.banned_until).toLocaleString("zh-CN")}` : "永久"}
                    </span>
                  </div>
                  <button onClick={() => handleRemoveBan(b.id)}
                    className="text-sm text-primary-500 hover:text-primary-400 flex items-center gap-1">
                    <UserX className="w-3.5 h-3.5" /> 解除
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {tab === "alts" && (
        <div className="bg-dark-card rounded-xl border border-dark-border divide-y divide-dark-border">
          {alts.length === 0 ? (
            <p className="text-center text-dark-muted py-8 text-sm">暂无小号</p>
          ) : (
            alts.map((a) => (
              <div key={a.alt_id} className="flex items-center justify-between px-5 py-3 text-sm">
                <span>🎭 <span className="font-medium">{a.alt_username}</span> (#{a.alt_id})</span>
                <span className="text-dark-muted">→ 主号 #{a.main_id}</span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
