import { useState, useRef } from "react";
import { Link } from "react-router-dom";
import type { UserBrief } from "../api";
import UserAvatar from "./UserAvatar";

interface Props {
  user: UserBrief;
  children: React.ReactNode;
}

export default function UserHoverCard({ user, children }: Props) {
  const [show, setShow] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout>>();

  const enter = () => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setShow(true), 300);
  };
  const leave = () => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setShow(false), 200);
  };

  const STAGE_LABEL: Record<string, string> = {
    newbie: "🌱 新手",
    active: "🔥 活跃",
    tired: "😴 倦怠",
    silent: "🤫 沉默",
    quit: "👋 退坛",
  };

  return (
    <span className="relative inline-block" onMouseEnter={enter} onMouseLeave={leave}>
      {children}
      {show && (
        <div
          className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-56 bg-white rounded-xl shadow-lg border border-gray-200 p-3 animate-in fade-in duration-150"
          onMouseEnter={enter}
          onMouseLeave={leave}
        >
          <div className="flex items-center gap-2.5 mb-2">
            <Link to={`/user/${user.id}`}>
              <UserAvatar user={user} size={36} />
            </Link>
            <div className="min-w-0">
              <Link to={`/user/${user.id}`} className="font-semibold text-sm text-gray-800 hover:text-primary truncate block">
                {user.username}
              </Link>
              {user.occupation && (
                <p className="text-xs text-gray-400 truncate">{user.occupation}</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3 text-xs text-gray-500 mb-1.5">
            <span>💰 {user.credits}</span>
            <span>{STAGE_LABEL[user.lifecycle_stage] || user.lifecycle_stage}</span>
          </div>
          {user.interests_tags && user.interests_tags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {user.interests_tags.slice(0, 4).map((t) => (
                <span key={t} className="text-[10px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded-full">{t}</span>
              ))}
            </div>
          )}
          {/* 小三角 */}
          <div className="absolute left-1/2 -translate-x-1/2 -bottom-1.5 w-3 h-3 bg-white border-r border-b border-gray-200 rotate-45" />
        </div>
      )}
    </span>
  );
}
