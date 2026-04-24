import type { UserBrief } from "../api";

interface Props {
  user: UserBrief | null;
  size?: number;
}

const COLORS = [
  "bg-indigo-500", "bg-pink-500", "bg-emerald-500", "bg-amber-500",
  "bg-cyan-500", "bg-rose-500", "bg-violet-500", "bg-teal-500",
];

export default function UserAvatar({ user, size = 40 }: Props) {
  if (user?.avatar_url) {
    return (
      <img
        src={user.avatar_url}
        alt={user.username}
        className="rounded-full object-cover"
        style={{ width: size, height: size }}
      />
    );
  }

  const name = user?.username ?? "?";
  const initial = name.charAt(0).toUpperCase();
  const colorIdx = user ? user.id % COLORS.length : 0;

  return (
    <div
      className={`${COLORS[colorIdx]} rounded-full flex items-center justify-center text-white font-bold`}
      style={{ width: size, height: size, fontSize: size * 0.45 }}
    >
      {initial}
    </div>
  );
}
