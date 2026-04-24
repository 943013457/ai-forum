const BASE = "/api";

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// ==================== 帖子 ====================
export const getPosts = (page = 1, sort = "latest", tag?: string) => {
  let url = `/posts?page=${page}&page_size=20&sort=${sort}`;
  if (tag) url += `&tag=${encodeURIComponent(tag)}`;
  return request<PaginatedResponse>(url);
};

export const getPost = (id: number) => request<PostDetail>(`/posts/${id}`);

export const votePoll = (postId: number, optionIndex: number) =>
  request(`/posts/${postId}/vote`, {
    method: "POST",
    body: JSON.stringify({ option_index: optionIndex }),
  });

// ==================== 用户 ====================
export const getUsers = (page = 1, sort = "credits") =>
  request<PaginatedResponse>(`/users?page=${page}&page_size=20&sort=${sort}`);

export const getUser = (id: number) => request<UserProfile>(`/users/${id}`);

export const getUserPosts = (id: number, page = 1) =>
  request<PaginatedResponse>(`/users/${id}/posts?page=${page}`);

export const getUserDebates = (id: number) =>
  request<Debate[]>(`/users/${id}/debates`);

// ==================== 评论 ====================
export const getComments = (postId: number, page = 1) =>
  request<PaginatedResponse>(`/comments/post/${postId}?page=${page}&page_size=50`);

// ==================== 标签 ====================
export const getTags = (sort = "count", limit = 50) =>
  request<TagItem[]>(`/tags?sort=${sort}&limit=${limit}`);

export const getTrendingTags = (limit = 10) =>
  request<TagItem[]>(`/tags/trending?limit=${limit}`);

// ==================== 管理 ====================
export const getEngineStatus = () => request<EngineStatus>(`/admin/engine/status`);
export const stopEngine = () => request(`/admin/engine/stop`, { method: "POST" });
export const generateUsers = (count = 50) =>
  request(`/admin/engine/generate-users?count=${count}`, { method: "POST" });
export const getEngineLogs = (limit = 50) =>
  request<EngineLog[]>(`/admin/engine/logs?limit=${limit}`);
export const getAdminStats = () => request<AdminStats>(`/admin/stats`);
export const getDailyTopics = () => request<DailyTopic[]>(`/admin/daily-topics`);

export const toggleFeatured = (postId: number) =>
  request(`/admin/posts/${postId}/feature`, { method: "POST" });
export const togglePinned = (postId: number) =>
  request(`/admin/posts/${postId}/pin`, { method: "POST" });
export const markRumor = (postId: number) =>
  request(`/admin/posts/${postId}/mark-rumor`, { method: "POST" });

export const getBans = () => request<Ban[]>(`/admin/bans`);
export const createBan = (data: { user_id: number; reason: string; duration?: string }) =>
  request(`/admin/bans`, { method: "POST", body: JSON.stringify(data) });
export const removeBan = (id: number) =>
  request(`/admin/bans/${id}`, { method: "DELETE" });

export const getAltAccounts = () => request<AltAccount[]>(`/admin/alt-accounts`);

export const getAnnouncements = () => request<AnnouncementItem[]>(`/admin/announcements`);
export const createAnnouncement = (data: {
  title: string; content: string; reward_credits: number;
  start_time: string; end_time: string;
}) => request(`/admin/announcements`, { method: "POST", body: JSON.stringify(data) });
export const deleteAnnouncement = (id: number) =>
  request(`/admin/announcements/${id}`, { method: "DELETE" });

export const getNewsImage = () => request<{ image_url: string | null }>(`/news-image`);

export const getActiveAnnouncements = () =>
  request<ActiveAnnouncement[]>(`/announcements/active`);

export const markForDelete = (postId: number) =>
  request<{ ok: boolean; marked_for_delete_at?: string }>(`/admin/posts/${postId}/mark-delete`, { method: "POST" });
export const unmarkForDelete = (postId: number) =>
  request<{ ok: boolean }>(`/admin/posts/${postId}/unmark-delete`, { method: "POST" });

export const updateDailyTopic = (topicId: number, data: { title?: string; description?: string }) =>
  request(`/admin/daily-topics/${topicId}`, { method: "PUT", body: JSON.stringify(data) });

// ==================== 类型 ====================
export interface PaginatedResponse {
  items: any[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface UserBrief {
  id: number;
  username: string;
  avatar_url: string | null;
  credits: number;
  lifecycle_stage: string;
  occupation: string | null;
  interests_tags: string[] | null;
}

export interface PostItem {
  id: number;
  author_id: number;
  title: string;
  content: string | null;
  summary: string | null;
  image_url: string | null;
  is_featured: boolean;
  is_pinned: boolean;
  is_rumor: boolean;
  is_poll: boolean;
  is_debate: boolean;
  is_repost: boolean;
  view_count: number;
  like_count: number;
  comment_count: number;
  marked_for_delete_at: string | null;
  created_at: string;
  author: UserBrief | null;
  tags: string[];
}

export interface CommentItem {
  id: number;
  post_id: number;
  author_id: number;
  content: string;
  parent_comment_id: number | null;
  created_at: string;
  author: UserBrief | null;
  replies: CommentItem[];
}

export interface PollData {
  id: number;
  post_id: number;
  options: string[];
  votes: Record<number, number>;
  total_votes: number;
}

export interface PostDetail extends PostItem {
  comments: CommentItem[];
  poll: PollData | null;
}

export interface Achievement {
  achievement_type: string;
  title: string;
  awarded_at: string;
}

export interface UserProfile {
  id: number;
  username: string;
  avatar_url: string | null;
  persona_text: string;
  age: number;
  occupation: string;
  education: string;
  language: string;
  personality_json: Record<string, number>;
  interests_tags: string[];
  expression_style: string;
  credits: number;
  mood: number;
  lifecycle_stage: string;
  alt_of: number | null;
  is_system: boolean;
  created_at: string;
  follower_count: number;
  following_count: number;
  post_count: number;
  comment_count: number;
  achievements: Achievement[];
  ban_status: Ban | null;
}

export interface TagItem {
  id: number;
  name: string;
  post_count: number;
}

export interface EngineStatus {
  running: boolean;
  tick_number: number;
  total_users: number;
  total_posts: number;
  total_comments: number;
  llm_calls_this_hour: number;
}

export interface EngineLog {
  id: number;
  tick_number: number;
  active_users_count: number;
  comments_generated: number;
  posts_generated: number;
  likes_generated: number;
  llm_calls: number;
  timestamp: string;
}

export interface AdminStats {
  total_users: number;
  total_posts: number;
  total_comments: number;
  today_posts: number;
  today_comments: number;
  active_debates: number;
}

export interface DailyTopic {
  id: number;
  title: string;
  description: string | null;
  date: string;
  post_count: number;
}

export interface Debate {
  id: number;
  post_id: number;
  user_a_id: number;
  user_b_id: number;
  topic: string;
  rounds: number;
  winner_id: number | null;
  status: string;
  created_at: string;
}

export interface Ban {
  id: number;
  user_id: number;
  reason: string;
  banned_until: string | null;
  created_by: string | null;
  created_at: string;
}

export interface AltAccount {
  alt_id: number;
  alt_username: string;
  main_id: number;
}

export interface AnnouncementItem {
  id: number;
  title: string;
  content: string;
  reward_credits: number;
  start_time: string;
  end_time: string;
  is_active: boolean;
  created_at: string;
}

export interface ActiveAnnouncement {
  id: number;
  title: string;
  content: string;
  reward_credits: number;
  end_time: string;
}
