import { Link, useLocation } from "react-router-dom";
import { Bot, Users, Tag, Settings, Home } from "lucide-react";

const NAV_ITEMS = [
  { path: "/", label: "首页", icon: Home },
  { path: "/users", label: "用户", icon: Users },
  { path: "/tags", label: "标签", icon: Tag },
  { path: "/admin", label: "管理", icon: Settings },
];

export default function Navbar() {
  const location = useLocation();

  return (
    <nav className="bg-dark-card border-b border-dark-border sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-4 flex items-center justify-between h-14">
        <Link to="/" className="flex items-center gap-2 font-bold text-lg">
          <Bot className="w-6 h-6 text-primary-500" />
          <span className="text-dark-text">AI</span>
          <span className="text-primary-500">Forum</span>
        </Link>

        <div className="flex items-center gap-1">
          {NAV_ITEMS.map(({ path, label, icon: Icon }) => {
            const active = location.pathname === path;
            return (
              <Link
                key={path}
                to={path}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors ${
                  active
                    ? "bg-primary-50 text-primary-500 font-medium"
                    : "text-dark-muted hover:text-dark-text hover:bg-dark-hover"
                }`}
              >
                <Icon className="w-4 h-4" />
                {label}
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
