import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getTags } from "../api";
import type { TagItem } from "../api";
import { Loader2, Hash } from "lucide-react";

export default function TagsPage() {
  const [tags, setTags] = useState<TagItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getTags("count", 100).then((t) => { setTags(t); setLoading(false); });
  }, []);

  if (loading) return <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 animate-spin text-primary-500" /></div>;

  const maxCount = Math.max(...tags.map((t) => t.post_count), 1);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6 flex items-center gap-2 text-dark-text">
        <Hash className="w-6 h-6 text-primary-500" /> 所有标签
      </h1>

      <div className="bg-dark-card rounded-xl border border-dark-border p-6">
        <div className="flex flex-wrap gap-3">
          {tags.map((tag) => {
            const ratio = tag.post_count / maxCount;
            const size = 0.75 + ratio * 0.5;
            return (
              <Link
                key={tag.id}
                to={`/?tag=${encodeURIComponent(tag.name)}`}
                className="inline-flex items-center gap-1 bg-primary-50 text-primary-600 rounded-full px-3 py-1 hover:bg-primary-100 transition-colors"
                style={{ fontSize: `${size}rem` }}
              >
                #{tag.name}
                <span className="text-primary-600/60 ml-1" style={{ fontSize: "0.75rem" }}>{tag.post_count}</span>
              </Link>
            );
          })}
          {tags.length === 0 && <p className="text-dark-muted text-sm">暂无标签</p>}
        </div>
      </div>
    </div>
  );
}
