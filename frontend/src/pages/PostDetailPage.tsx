import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { getPost, getComments, likeComment, votePoll, toggleFeatured, markForDelete, unmarkForDelete } from "../api";
import type { PostDetail, CommentItem } from "../api";
import UserAvatar from "../components/UserAvatar";
import UserHoverCard from "../components/UserHoverCard";
import MarkdownContent from "../components/MarkdownContent";
import { Heart, MessageCircle, Eye, ArrowLeft, Loader2, BarChart3, Star, FileText, Code, Trash2, ThumbsUp, ArrowUpDown, ChevronDown } from "lucide-react";
import dayjs from "dayjs";

/** 将评论文本中的 @用户名 渲染为可点击链接 */
function RenderCommentContent({ content, comment }: { content: string; comment: CommentItem }) {
  // 解析 "回复 @用户名：" 前缀
  const match = content.match(/^回复\s*@([^：:]+)[：:]\s*/);
  if (match) {
    const mentionName = match[1];
    const rest = content.slice(match[0].length);
    // 尝试找到被回复的作者信息
    return (
      <div className="text-sm text-dark-text mt-1">
        <span className="text-dark-muted">回复 </span>
        <Link to={`/?tag=`} onClick={(e) => e.preventDefault()}
          className="text-primary-400 hover:text-primary-500 hover:underline font-medium">
          @{mentionName}
        </Link>
        <span className="text-dark-muted">：</span>
        <MarkdownContent content={rest} className="inline text-dark-text" />
      </div>
    );
  }
  return <MarkdownContent content={content} className="text-sm text-dark-text mt-1" />;
}

function CommentTree({ comment, depth = 0, maxDepth = 3, onLike }: {
  comment: CommentItem; depth?: number; maxDepth?: number;
  onLike: (commentId: number) => void;
}) {
  return (
    <div className={`${depth > 0 ? "ml-8 border-l-2 border-dark-border pl-4" : ""}`}>
      <div className="flex gap-3 py-3">
        <Link to={`/user/${comment.author_id}`}>
          {comment.author ? (
            <UserHoverCard user={comment.author}>
              <UserAvatar user={comment.author} size={32} />
            </UserHoverCard>
          ) : (
            <UserAvatar user={comment.author} size={32} />
          )}
        </Link>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 text-sm">
            {comment.author ? (
              <UserHoverCard user={comment.author}>
                <Link to={`/user/${comment.author_id}`} className="font-medium text-dark-text hover:text-primary-500">
                  {comment.author.username}
                </Link>
              </UserHoverCard>
            ) : (
              <span className="font-medium text-dark-text">用户#{comment.author_id}</span>
            )}
            <span className="text-xs text-dark-muted">{dayjs(comment.created_at).format("MM-DD HH:mm")}</span>
          </div>
          <RenderCommentContent content={comment.content} comment={comment} />
          {/* 点赞按钮 */}
          <button
            onClick={() => onLike(comment.id)}
            className={`mt-1.5 flex items-center gap-1 text-xs transition-colors ${
              comment.like_count > 0 ? "text-primary-500" : "text-dark-muted hover:text-primary-500"
            }`}
          >
            <ThumbsUp className="w-3.5 h-3.5" />
            {comment.like_count > 0 && <span>{comment.like_count}</span>}
          </button>
        </div>
      </div>
      {depth < maxDepth - 1 && comment.replies?.map((r) => (
        <CommentTree key={r.id} comment={r} depth={depth + 1} maxDepth={maxDepth} onLike={onLike} />
      ))}
      {depth >= maxDepth - 1 && comment.replies && comment.replies.length > 0 && (
        <p className="text-xs text-dark-muted ml-8 py-1">
          还有 {comment.replies.length} 条更深层回复…
        </p>
      )}
    </div>
  );
}

export default function PostDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [post, setPost] = useState<PostDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [showRaw, setShowRaw] = useState(false);
  const [stickyVisible, setStickyVisible] = useState(false);
  const titleRef = useRef<HTMLHeadingElement>(null);

  // 评论分页状态
  const [comments, setComments] = useState<CommentItem[]>([]);
  const [commentSort, setCommentSort] = useState<"mixed" | "likes" | "latest">("mixed");
  const [commentPage, setCommentPage] = useState(1);
  const [commentTotal, setCommentTotal] = useState(0);
  const [commentPages, setCommentPages] = useState(0);
  const [commentLoading, setCommentLoading] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    getPost(Number(id)).then((p) => { setPost(p); setLoading(false); });
  }, [id]);

  // 加载评论
  const loadComments = useCallback(async (page: number, sort: string, append = false) => {
    if (!id) return;
    setCommentLoading(true);
    try {
      const res = await getComments(Number(id), page, sort);
      const items = res.items as CommentItem[];
      setComments((prev) => append ? [...prev, ...items] : items);
      setCommentTotal(res.total);
      setCommentPages(res.pages);
      setCommentPage(page);
    } catch { /* ignore */ }
    setCommentLoading(false);
  }, [id]);

  // 帖子加载后加载首页评论
  useEffect(() => {
    if (post) loadComments(1, commentSort);
  }, [post?.id, commentSort]);

  // 滚动监听：标题滚出视口时显示吸顶
  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => setStickyVisible(!entry.isIntersecting),
      { threshold: 0 }
    );
    if (titleRef.current) observer.observe(titleRef.current);
    return () => observer.disconnect();
  }, [post]);

  const handleVote = async (optionIndex: number) => {
    if (!post) return;
    await votePoll(post.id, optionIndex);
    const updated = await getPost(post.id);
    setPost(updated);
  };

  const handleFeature = async () => {
    if (!post) return;
    const res = await toggleFeatured(post.id) as any;
    setPost({ ...post, is_featured: res.is_featured });
  };

  const handleMarkDelete = async () => {
    if (!post) return;
    if (post.marked_for_delete_at) {
      await unmarkForDelete(post.id);
      setPost({ ...post, marked_for_delete_at: null });
    } else {
      const res = await markForDelete(post.id);
      setPost({ ...post, marked_for_delete_at: res.marked_for_delete_at || new Date().toISOString() });
    }
  };

  // 评论点赞（递归更新嵌套评论的 like_count）
  const handleCommentLike = async (commentId: number) => {
    if (!post) return;
    try {
      const res = await likeComment(post.id, commentId);
      const updateLike = (list: CommentItem[]): CommentItem[] =>
        list.map((c) =>
          c.id === commentId
            ? { ...c, like_count: res.like_count }
            : { ...c, replies: updateLike(c.replies || []) }
        );
      setComments((prev) => updateLike(prev));
    } catch { /* ignore */ }
  };

  const handleLoadMore = () => {
    if (commentPage < commentPages) {
      loadComments(commentPage + 1, commentSort, true);
    }
  };

  if (loading) {
    return <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 animate-spin text-primary-500" /></div>;
  }
  if (!post) {
    return <div className="text-center py-20 text-dark-muted">帖子不存在</div>;
  }

  const isHotNews = post.author?.username === "热点快讯";

  return (
    <div className="max-w-3xl mx-auto">
      {/* 吸顶标题栏（紧贴 Navbar 下方） */}
      {stickyVisible && (
        <div className="fixed top-14 left-0 right-0 z-40 bg-dark-card/95 backdrop-blur border-b border-dark-border">
          <div className="max-w-3xl mx-auto px-4 py-2 flex items-center gap-3">
            <Link to="/" className="text-dark-muted hover:text-primary-500 shrink-0">
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <h2 className="font-semibold text-sm text-dark-text truncate">{post.title}</h2>
            <span className="ml-auto text-xs text-dark-muted shrink-0">
              {post.comment_count} 评论
            </span>
          </div>
        </div>
      )}

      <Link to="/" className="inline-flex items-center gap-1 text-sm text-dark-muted hover:text-primary-500 mb-4">
        <ArrowLeft className="w-4 h-4" /> 返回首页
      </Link>

      {/* 删除警告 */}
      {post.marked_for_delete_at && (() => {
        const deleteTime = dayjs(post.marked_for_delete_at).add(24, 'hour');
        const diff = deleteTime.diff(dayjs(), 'minute');
        const hours = Math.floor(Math.max(0, diff) / 60);
        const mins = Math.max(0, diff) % 60;
        return (
          <div className="bg-primary-50 border border-primary-300/30 rounded-xl p-3 mb-3 flex items-center gap-2">
            <Trash2 className="w-4 h-4 text-primary-500 shrink-0" />
            <p className="text-sm text-primary-500">
              该帖子已被标记删除，将在 <strong>{hours}h{mins}m</strong> 后自动删除（评论同步清除）。已禁止新评论。
            </p>
          </div>
        );
      })()}

      {/* 帖子主体 */}
      <article className={`bg-dark-card rounded-xl border p-6 ${post.marked_for_delete_at ? 'border-primary-300/30' : 'border-dark-border'}`}>
        <div className="flex items-center gap-3 mb-4">
          <Link to={`/user/${post.author_id}`}>
            {post.author ? (
              <UserHoverCard user={post.author}>
                <UserAvatar user={post.author} size={44} />
              </UserHoverCard>
            ) : (
              <UserAvatar user={post.author} size={44} />
            )}
          </Link>
          <div>
            {post.author ? (
              <UserHoverCard user={post.author}>
                <Link to={`/user/${post.author_id}`} className="font-medium text-dark-text hover:text-primary-500">
                  {post.author.username}
                </Link>
              </UserHoverCard>
            ) : (
              <span className="font-medium text-dark-text">用户#{post.author_id}</span>
            )}
            <p className="text-xs text-dark-muted">{dayjs(post.created_at).format("YYYY-MM-DD HH:mm")}</p>
          </div>
        </div>

        <h1 ref={titleRef} className="text-2xl font-bold text-dark-text mb-3">{post.title}</h1>

        {/* badges + 操作 */}
        <div className="flex gap-2 mb-4 flex-wrap items-center">
          {post.is_featured && <span className="text-xs bg-amber-900/30 text-amber-400 px-2 py-0.5 rounded-full">⭐ 精选</span>}
          {post.is_rumor && <span className="text-xs bg-orange-900/30 text-orange-400 px-2 py-0.5 rounded-full">⚠️ 未证实</span>}
          {post.is_debate && <span className="text-xs bg-purple-900/30 text-purple-400 px-2 py-0.5 rounded-full">🥊 约架</span>}
          {post.is_repost && <span className="text-xs bg-dark-surface text-dark-muted px-2 py-0.5 rounded-full">🔄 转发</span>}
          {post.tags.map((t) => (
            <Link key={t} to={`/?tag=${encodeURIComponent(t)}`}
              className="text-xs bg-primary-50 text-primary-600 px-2 py-0.5 rounded-full hover:bg-primary-100">
              #{t}
            </Link>
          ))}
          {/* 操作按钮 */}
          <div className="ml-auto flex items-center gap-1.5">
            <button
              onClick={handleFeature}
              className={`flex items-center gap-1 text-xs px-2.5 py-1 rounded-full border transition-colors ${
                post.is_featured
                  ? "bg-amber-900/30 border-amber-800 text-amber-400 hover:bg-amber-900/50"
                  : "bg-dark-surface border-dark-border text-dark-muted hover:bg-primary-50 hover:text-primary-500"
              }`}
              title={post.is_featured ? "取消精选" : "设为精选"}
            >
              <Star className="w-3 h-3" /> {post.is_featured ? "取消精选" : "精选"}
            </button>
            <button
              onClick={handleMarkDelete}
              className={`flex items-center gap-1 text-xs px-2.5 py-1 rounded-full border transition-colors ${
                post.marked_for_delete_at
                  ? "bg-primary-50 border-primary-300/30 text-primary-500 hover:bg-primary-100"
                  : "bg-dark-surface border-dark-border text-dark-muted hover:bg-primary-50 hover:text-primary-500"
              }`}
              title={post.marked_for_delete_at ? "取消删除标记" : "标记删除（24h后自动删除）"}
            >
              <Trash2 className="w-3 h-3" /> {post.marked_for_delete_at ? "取消删除" : "标记删除"}
            </button>
          </div>
        </div>

        {post.image_url && (
          <img src={post.image_url} alt="" className="rounded-lg mb-4 max-h-96 object-cover w-full" />
        )}

        {post.content && (
          <div>
            {/* 热点新闻切换按钮 */}
            {isHotNews && (
              <div className="flex justify-end mb-2">
                <button
                  onClick={() => setShowRaw(!showRaw)}
                  className="flex items-center gap-1 text-xs text-dark-muted hover:text-primary-500 transition-colors"
                >
                  {showRaw ? <Code className="w-3.5 h-3.5" /> : <FileText className="w-3.5 h-3.5" />}
                  {showRaw ? "Markdown 渲染" : "查看原文"}
                </button>
              </div>
            )}
            {showRaw ? (
              <pre className="text-sm text-dark-text whitespace-pre-wrap bg-dark-surface rounded-lg p-4 overflow-x-auto">{post.content}</pre>
            ) : (
              <MarkdownContent content={post.content} className="text-dark-text leading-relaxed" />
            )}
          </div>
        )}

        {/* 投票 */}
        {post.poll && (
          <div className="mt-4 bg-blue-900/20 rounded-lg p-4 border border-blue-900/30">
            <h4 className="font-medium text-sm text-blue-400 flex items-center gap-1 mb-3">
              <BarChart3 className="w-4 h-4" /> 投票（{post.poll.total_votes} 票）
            </h4>
            <div className="space-y-2">
              {post.poll.options.map((opt: string, idx: number) => {
                const votes = post.poll!.votes[idx] || 0;
                const pct = post.poll!.total_votes > 0 ? Math.round((votes / post.poll!.total_votes) * 100) : 0;
                return (
                  <button
                    key={idx}
                    onClick={() => handleVote(idx)}
                    className="w-full text-left bg-dark-surface border border-dark-border rounded-lg px-4 py-2 hover:bg-dark-hover transition-colors relative overflow-hidden"
                  >
                    <div className="absolute left-0 top-0 h-full bg-blue-900/30" style={{ width: `${pct}%` }} />
                    <div className="relative flex justify-between">
                      <span className="text-sm">{opt}</span>
                      <span className="text-xs text-blue-400 font-medium">{pct}% ({votes})</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* 统计 */}
        <div className="flex items-center gap-5 mt-6 pt-4 border-t border-dark-border text-sm text-dark-muted">
          <span className="flex items-center gap-1"><Heart className="w-4 h-4" /> {post.like_count}</span>
          <span className="flex items-center gap-1"><MessageCircle className="w-4 h-4" /> {post.comment_count}</span>
          <span className="flex items-center gap-1"><Eye className="w-4 h-4" /> {post.view_count}</span>
        </div>
      </article>

      {/* 评论区 */}
      <section className="bg-dark-card rounded-xl border border-dark-border mt-4 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-dark-text">评论 ({commentTotal})</h3>
          {!post.marked_for_delete_at && commentTotal > 0 && (
            <div className="flex items-center gap-1 text-xs">
              <ArrowUpDown className="w-3.5 h-3.5 text-dark-muted" />
              {(["mixed", "likes", "latest"] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => setCommentSort(s)}
                  className={`px-2 py-0.5 rounded-full transition-colors ${
                    commentSort === s
                      ? "bg-primary-50 text-primary-500 font-medium"
                      : "text-dark-muted hover:text-dark-text"
                  }`}
                >
                  {{ mixed: "综合", likes: "最热", latest: "最新" }[s]}
                </button>
              ))}
            </div>
          )}
        </div>
        {post.marked_for_delete_at ? (
          <p className="text-sm text-primary-500 py-8 text-center">该帖子已被标记删除，评论功能已禁用</p>
        ) : comments.length === 0 && !commentLoading ? (
          <p className="text-sm text-dark-muted py-8 text-center">暂无评论</p>
        ) : (
          <>
            <div className="divide-y divide-dark-border">
              {comments.map((c) => (
                <CommentTree key={c.id} comment={c} maxDepth={3} onLike={handleCommentLike} />
              ))}
            </div>
            {/* 加载更多 */}
            {commentPage < commentPages && (
              <button
                onClick={handleLoadMore}
                disabled={commentLoading}
                className="w-full mt-4 py-2.5 text-sm text-dark-muted hover:text-primary-500 bg-dark-surface hover:bg-primary-50 rounded-lg transition-colors flex items-center justify-center gap-1.5"
              >
                {commentLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    <ChevronDown className="w-4 h-4" />
                    加载更多评论（{comments.length}/{commentTotal}）
                  </>
                )}
              </button>
            )}
            {commentLoading && comments.length === 0 && (
              <div className="flex justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-dark-muted" />
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}
