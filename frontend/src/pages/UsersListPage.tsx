import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getUsers } from "../api";
import type { UserBrief } from "../api";
import UserAvatar from "../components/UserAvatar";
import { Loader2, Crown } from "lucide-react";

export default function UsersListPage() {
  const [users, setUsers] = useState<UserBrief[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [sort, setSort] = useState("credits");

  useEffect(() => {
    setLoading(true);
    getUsers(page, sort).then((res) => {
      setUsers(res.items as UserBrief[]);
      setPages(res.pages);
      setLoading(false);
    });
  }, [page, sort]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-dark-text">用户排行</h1>
        <div className="flex bg-dark-card border border-dark-border rounded-lg p-0.5">
          {[
            { key: "credits", label: "积分" },
            { key: "newest", label: "最新" },
          ].map(({ key, label }) => (
            <button
              key={key}
              onClick={() => { setSort(key); setPage(1); }}
              className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                sort === key ? "bg-primary-500 text-white font-medium" : "text-dark-muted"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 animate-spin text-primary-500" /></div>
      ) : (
        <div className="bg-dark-card rounded-xl border border-dark-border divide-y divide-dark-border">
          {users.map((user, idx) => (
            <Link
              key={user.id}
              to={`/user/${user.id}`}
              className="flex items-center gap-4 px-5 py-3 hover:bg-dark-hover transition-colors"
            >
              <span className="text-sm font-bold text-dark-muted w-6 text-right">
                {(page - 1) * 20 + idx + 1}
              </span>
              <UserAvatar user={user} size={40} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-dark-text truncate">{user.username}</span>
                  <span className="text-xs bg-dark-surface text-dark-muted px-1.5 py-0.5 rounded-full">{user.lifecycle_stage}</span>
                </div>
              </div>
              <div className="flex items-center gap-1 text-sm">
                <Crown className="w-4 h-4 text-amber-500" />
                <span className="font-semibold text-amber-400">{user.credits}</span>
              </div>
            </Link>
          ))}
        </div>
      )}

      {pages > 1 && (
        <div className="flex justify-center gap-2 pt-6">
          <button disabled={page <= 1} onClick={() => setPage(page - 1)}
            className="px-3 py-1.5 rounded-lg border border-dark-border text-sm text-dark-text disabled:opacity-40 hover:bg-dark-hover">上一页</button>
          <span className="px-3 py-1.5 text-sm text-dark-muted">{page} / {pages}</span>
          <button disabled={page >= pages} onClick={() => setPage(page + 1)}
            className="px-3 py-1.5 rounded-lg border border-dark-border text-sm text-dark-text disabled:opacity-40 hover:bg-dark-hover">下一页</button>
        </div>
      )}
    </div>
  );
}
