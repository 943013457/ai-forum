import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Link } from "react-router-dom";

interface Props {
  content: string;
  className?: string;
}

export default function MarkdownContent({ content, className = "" }: Props) {
  return (
    <div className={`prose prose-sm max-w-none prose-gray ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // 链接在新窗口打开
          a: ({ href, children, ...props }) => (
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary-600 hover:underline" {...props}>
              {children}
            </a>
          ),
          // 标签 #xxx 转为路由链接
          p: ({ children, ...props }) => {
            if (!children) return <p {...props}>{children}</p>;
            const processed = processHashTags(children);
            return <p {...props}>{processed}</p>;
          },
          // 表格样式
          table: ({ children, ...props }) => (
            <div className="overflow-x-auto">
              <table className="min-w-full border-collapse border border-gray-200" {...props}>{children}</table>
            </div>
          ),
          th: ({ children, ...props }) => (
            <th className="border border-gray-200 bg-gray-50 px-3 py-1.5 text-left text-xs font-semibold" {...props}>{children}</th>
          ),
          td: ({ children, ...props }) => (
            <td className="border border-gray-200 px-3 py-1.5 text-sm" {...props}>{children}</td>
          ),
          // 代码块
          code: ({ className: codeClass, children, ...props }) => {
            const isInline = !codeClass;
            return isInline ? (
              <code className="bg-gray-100 text-red-600 px-1 py-0.5 rounded text-xs" {...props}>{children}</code>
            ) : (
              <code className={`${codeClass} block bg-gray-900 text-gray-100 p-3 rounded-lg text-xs overflow-x-auto`} {...props}>{children}</code>
            );
          },
          // 图片
          img: ({ src, alt, ...props }) => (
            <img src={src} alt={alt || ""} className="rounded-lg max-h-96 object-cover" loading="lazy" referrerPolicy="no-referrer" {...props} />
          ),
          // blockquote
          blockquote: ({ children, ...props }) => (
            <blockquote className="border-l-4 border-primary-300 bg-primary-50 pl-4 py-2 my-2 text-sm italic text-gray-600" {...props}>
              {children}
            </blockquote>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

/** 将文本中的 #标签 和 @用户 转为可点击链接 */
function processHashTags(children: React.ReactNode): React.ReactNode {
  if (typeof children === "string") {
    // 匹配 #标签、@username(uid:123)、旧格式 @数字
    const pattern = /(#[\u4e00-\u9fa5a-zA-Z0-9_]+|@([^(@\s]+)\(uid:(\d+)\)|@(\d+))/g;
    const result: React.ReactNode[] = [];
    let last = 0;
    let match: RegExpExecArray | null;
    while ((match = pattern.exec(children)) !== null) {
      if (match.index > last) result.push(<span key={`t${last}`}>{children.slice(last, match.index)}</span>);
      if (match[0].startsWith("#")) {
        result.push(
          <Link key={`h${match.index}`} to={`/?tag=${encodeURIComponent(match[0].slice(1))}`}
            className="text-primary-600 hover:text-primary-800 hover:underline">{match[0]}</Link>
        );
      } else if (match[2] && match[3]) {
        // @username(uid:123)
        result.push(
          <Link key={`u${match.index}`} to={`/user/${match[3]}`}
            className="text-primary-500 hover:text-primary-700 hover:underline font-medium">@{match[2]}</Link>
        );
      } else if (match[4]) {
        // 旧格式 @数字
        result.push(
          <Link key={`u${match.index}`} to={`/user/${match[4]}`}
            className="text-primary-500 hover:text-primary-700 hover:underline font-medium">@用户#{match[4]}</Link>
        );
      }
      last = match.index + match[0].length;
    }
    if (last === 0) return children;
    if (last < children.length) result.push(<span key={`t${last}`}>{children.slice(last)}</span>);
    return result;
  }
  if (Array.isArray(children)) {
    return children.map((child, i) => <span key={i}>{processHashTags(child)}</span>);
  }
  return children;
}
