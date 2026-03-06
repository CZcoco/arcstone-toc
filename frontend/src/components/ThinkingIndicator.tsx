export default function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-3 py-2 animate-fade-in">
      <div className="flex items-center gap-1">
        <span className="w-1.5 h-1.5 rounded-full bg-accent/60 animate-pulse-soft" style={{ animationDelay: "0ms" }} />
        <span className="w-1.5 h-1.5 rounded-full bg-accent/60 animate-pulse-soft" style={{ animationDelay: "400ms" }} />
        <span className="w-1.5 h-1.5 rounded-full bg-accent/60 animate-pulse-soft" style={{ animationDelay: "800ms" }} />
      </div>
      <span className="text-xs text-sand-400">思考中</span>
    </div>
  );
}
