import { Link } from "react-router-dom";
import { Heart, MessageCircle, Eye, Pin, Star, AlertTriangle, BarChart3, Swords, Trash2 } from "lucide-react";
import type { PostItem } from "../api";
import UserAvatar from "./UserAvatar";
import dayjs from "dayjs";

interface Props {
  post: PostItem;
}

function DeleteCountdown({ markedAt }: { markedAt: string }) {
  const deleteTime = dayjs(markedAt).add(24, "hour");
  const now = dayjs();
  const diff = deleteTime.diff(now, "minute");
  if (diff <= 0) return <span className="text-red-600 text-xs font-medium">即将删除</span>;
  const hours = Math.floor(diff / 60);
  const mins = diff % 60;
  return (
    <span className="inline-flex items-center gap-0.5 text-xs bg-red-50 text-red-600 px-1.5 py-0.5 rounded-full font-medium">
      <Trash2 className="w-3 h-3" /> {hours}h{mins}m 后删除
    </span>
  );
}

const LANG_FLAGS: Record<string, string> = { en: "🇬🇧", ja: "🇯🇵", ko: "🇰🇷" };

export default function PostCard({ post }: Props) {
  const isMarkedDelete = !!post.marked_for_delete_at;

  return (
    <div className={`bg-white rounded-xl border p-4 hover:shadow-md transition-shadow ${
      isMarkedDelete ? "border-red-200 bg-red-50/30" : "border-gray-200"
    }`}>
      <div className="flex items-start gap-3">
        <Link to={`/user/${post.author_id}`}>
          <UserAvatar user={post.author} size={40} />
        </Link>
        <div className="flex-1 min-w-0">
          {/* badges */}
          <div className="flex items-center gap-1.5 mb-1 flex-wrap">
            {isMarkedDelete && <DeleteCountdown markedAt={post.marked_for_delete_at!} />}
            {post.is_pinned && (
              <span className="inline-flex items-center gap-0.5 text-xs bg-red-50 text-red-600 px-1.5 py-0.5 rounded-full font-medium">
                <Pin className="w-3 h-3" /> 置顶
              </span>
            )}
            {post.is_featured && (
              <span className="inline-flex items-center gap-0.5 text-xs bg-amber-50 text-amber-600 px-1.5 py-0.5 rounded-full font-medium">
                <Star className="w-3 h-3" /> 精选
              </span>
            )}
            {post.is_rumor && (
              <span className="inline-flex items-center gap-0.5 text-xs bg-orange-50 text-orange-600 px-1.5 py-0.5 rounded-full font-medium">
                <AlertTriangle className="w-3 h-3" /> 未证实
              </span>
            )}
            {post.is_poll && (
              <span className="inline-flex items-center gap-0.5 text-xs bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded-full font-medium">
                <BarChart3 className="w-3 h-3" /> 投票
              </span>
            )}
            {post.is_debate && (
              <span className="inline-flex items-center gap-0.5 text-xs bg-purple-50 text-purple-600 px-1.5 py-0.5 rounded-full font-medium">
                <Swords className="w-3 h-3" /> 约架
              </span>
            )}
            {post.is_repost && (
              <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded-full">转发</span>
            )}
          </div>

          {/* title */}
          <Link to={`/post/${post.id}`} className="block">
            <h3 className="font-semibold text-gray-900 hover:text-primary transition-colors line-clamp-2">
              {post.title}
            </h3>
          </Link>

          {/* summary */}
          {post.summary && (
            <p className="text-sm text-gray-500 mt-1 line-clamp-2">{post.summary}</p>
          )}

          {/* image */}
          {post.image_url && (
            <img
              src={post.image_url}
              alt=""
              className="mt-2 rounded-lg max-h-48 object-cover w-full"
              loading="lazy"
            />
          )}

          {/* tags */}
          {post.tags.length > 0 && (
            <div className="flex gap-1.5 mt-2 flex-wrap">
              {post.tags.map((t) => (
                <Link
                  key={t}
                  to={`/?tag=${encodeURIComponent(t)}`}
                  className="text-xs bg-primary-50 text-primary-700 px-2 py-0.5 rounded-full hover:bg-primary-100 transition-colors"
                >
                  #{t}
                </Link>
              ))}
            </div>
          )}

          {/* footer */}
          <div className="flex items-center gap-4 mt-3 text-xs text-gray-400">
            <span className="flex items-center gap-1"><Heart className="w-3.5 h-3.5" /> {post.like_count}</span>
            <span className="flex items-center gap-1"><MessageCircle className="w-3.5 h-3.5" /> {post.comment_count}</span>
            <span className="flex items-center gap-1"><Eye className="w-3.5 h-3.5" /> {post.view_count}</span>
            <span className="ml-auto">{dayjs(post.created_at).format("MM-DD HH:mm")}</span>
            {post.author && <span className="text-gray-500">{post.author.username}</span>}
          </div>
        </div>
      </div>
    </div>
  );
}
