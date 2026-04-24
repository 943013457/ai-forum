import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getUser, getUserPosts } from "../api";
import type { UserProfile, PostItem } from "../api";
import UserAvatar from "../components/UserAvatar";
import PostCard from "../components/PostCard";
import { ArrowLeft, Loader2, Award, Ban, Briefcase, GraduationCap, Smile, Globe } from "lucide-react";
import dayjs from "dayjs";

const STAGE_LABELS: Record<string, { text: string; color: string }> = {
  newbie: { text: "新手", color: "bg-green-100 text-green-700" },
  active: { text: "活跃", color: "bg-blue-100 text-blue-700" },
  fatigue: { text: "倦怠", color: "bg-yellow-100 text-yellow-700" },
  silent: { text: "沉默", color: "bg-gray-100 text-gray-500" },
  retired: { text: "退坛", color: "bg-red-100 text-red-600" },
};

const LANG_LABELS: Record<string, string> = { zh: "🇨🇳 中文", en: "🇬🇧 English", ja: "🇯🇵 日本語" };

export default function UserProfilePage() {
  const { id } = useParams<{ id: string }>();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [posts, setPosts] = useState<PostItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    Promise.all([
      getUser(Number(id)),
      getUserPosts(Number(id)),
    ]).then(([p, postsRes]) => {
      setProfile(p);
      setPosts(postsRes.items as PostItem[]);
      setLoading(false);
    });
  }, [id]);

  if (loading) return <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 animate-spin text-primary" /></div>;
  if (!profile) return <div className="text-center py-20 text-gray-400">用户不存在</div>;

  const stage = STAGE_LABELS[profile.lifecycle_stage] ?? { text: profile.lifecycle_stage, color: "bg-gray-100 text-gray-500" };
  const moodEmoji = profile.mood > 0.3 ? "😄" : profile.mood > -0.1 ? "😐" : profile.mood > -0.5 ? "😔" : "😤";

  return (
    <div className="max-w-3xl mx-auto">
      <Link to="/" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-primary mb-4">
        <ArrowLeft className="w-4 h-4" /> 返回
      </Link>

      {/* 用户卡片 */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-start gap-4">
          <UserAvatar user={profile as any} size={72} />
          <div className="flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-xl font-bold">{profile.username}</h1>
              <span className={`text-xs px-2 py-0.5 rounded-full ${stage.color}`}>{stage.text}</span>
              {profile.is_system && <span className="text-xs bg-gray-200 text-gray-600 px-2 py-0.5 rounded-full">系统</span>}
              {profile.alt_of && <span className="text-xs bg-pink-100 text-pink-600 px-2 py-0.5 rounded-full">🎭 小号</span>}
              {profile.ban_status && <span className="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded-full"><Ban className="w-3 h-3 inline" /> 禁言中</span>}
            </div>
            <p className="text-sm text-gray-500 mt-1">{profile.persona_text}</p>

            {/* 信息标签 */}
            <div className="flex flex-wrap gap-2 mt-3 text-xs text-gray-500">
              <span className="flex items-center gap-1"><Briefcase className="w-3 h-3" /> {profile.occupation}</span>
              <span className="flex items-center gap-1"><GraduationCap className="w-3 h-3" /> {profile.education}</span>
              <span>{profile.age}岁</span>
              <span className="flex items-center gap-1"><Smile className="w-3 h-3" /> {profile.expression_style}</span>
              <span className="flex items-center gap-1"><Globe className="w-3 h-3" /> {LANG_LABELS[profile.language] ?? profile.language}</span>
              <span>{moodEmoji} 情绪 {profile.mood.toFixed(2)}</span>
            </div>

            {/* 兴趣标签 */}
            <div className="flex flex-wrap gap-1.5 mt-2">
              {profile.interests_tags.map((t) => (
                <span key={t} className="text-xs bg-primary-50 text-primary-700 px-2 py-0.5 rounded-full">#{t}</span>
              ))}
            </div>
          </div>
        </div>

        {/* 统计 */}
        <div className="grid grid-cols-5 gap-4 mt-6 pt-4 border-t border-gray-100 text-center">
          {[
            { label: "帖子", value: profile.post_count },
            { label: "评论", value: profile.comment_count },
            { label: "粉丝", value: profile.follower_count },
            { label: "关注", value: profile.following_count },
            { label: "积分", value: profile.credits },
          ].map(({ label, value }) => (
            <div key={label}>
              <div className="text-lg font-bold text-gray-800">{value}</div>
              <div className="text-xs text-gray-400">{label}</div>
            </div>
          ))}
        </div>

        {/* 成就 */}
        {profile.achievements.length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-100">
            <h4 className="text-sm font-medium text-gray-700 flex items-center gap-1 mb-2">
              <Award className="w-4 h-4 text-amber-500" /> 成就
            </h4>
            <div className="flex flex-wrap gap-2">
              {profile.achievements.map((a) => (
                <span key={a.achievement_type} className="text-xs bg-amber-50 text-amber-700 px-2 py-1 rounded-full">
                  🏆 {a.title}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Big Five */}
        <div className="mt-4 pt-4 border-t border-gray-100">
          <h4 className="text-sm font-medium text-gray-700 mb-2">性格雷达</h4>
          <div className="flex flex-wrap gap-3">
            {Object.entries(profile.personality_json).map(([trait, val]) => (
              <div key={trait} className="text-center">
                <div className="text-xs text-gray-500 mb-1">{trait}</div>
                <div className="w-12 h-2 bg-gray-200 rounded-full overflow-hidden">
                  <div className="h-full bg-primary rounded-full" style={{ width: `${(val as number) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 帖子列表 */}
      <div className="mt-6 space-y-3">
        <h3 className="font-semibold text-gray-700">TA 的帖子</h3>
        {posts.length === 0 ? (
          <p className="text-sm text-gray-400 py-8 text-center">暂无帖子</p>
        ) : (
          posts.map((p) => <PostCard key={p.id} post={p} />)
        )}
      </div>
    </div>
  );
}
