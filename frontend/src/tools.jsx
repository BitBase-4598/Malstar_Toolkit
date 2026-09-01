import { lazy } from "react";
import { CalendarDays, ClipboardList, Download, FileText, FolderOpen, Inbox, LayoutDashboard, MessageCircle, Plus, RefreshCw, ScrollText, Upload } from "lucide-react";
import LeaveForecast from "./LeaveForecast";
import Dashboard from "./Dashboard";

function lazyTool(loader) {
  const Component = lazy(loader);
  Component.preload = loader;
  return Component;
}

const RecordsWorkspace = lazyTool(() => import("./RecordsWorkspace"));
const FeedbackWorkspace = lazyTool(() => import("./FeedbackWorkspace"));
const FileManager = lazyTool(() => import("./FileManager"));
const SopWorkspace = lazyTool(() => import("./SopWorkspace"));
const AskWorkspace = lazyTool(() => import("./AskWorkspace"));
const ActivityLog = lazyTool(() => import("./ActivityLog"));

function SearchActions({ recordsRef, recordsImporting }) {
  return (
    <>
      <button className="ghost" type="button" onClick={() => recordsRef.current?.openUpload()} disabled={recordsImporting}>
        <Upload size={16} />
        {recordsImporting ? "Importing..." : "Import CSV"}
      </button>
      <button className="primary" type="button" onClick={() => recordsRef.current?.openNew()}>
        <Plus size={16} />
        Add record
      </button>
    </>
  );
}

function DashboardActions({ dashRef, dashImporting, dashPage, lclRef, lclImporting, gcaRef, gcaImporting }) {
  if (dashPage === "lcl") {
    return (
      <button className="primary" type="button" onClick={() => lclRef.current?.openImport()} disabled={lclImporting}>
        <Upload size={16} />
        {lclImporting ? "Importing..." : "Re-import"}
      </button>
    );
  }
  if (dashPage === "gca") {
    return (
      <button className="primary" type="button" onClick={() => gcaRef.current?.openImport()} disabled={gcaImporting}>
        <Upload size={16} />
        {gcaImporting ? "Importing..." : "Re-import"}
      </button>
    );
  }
  return (
    <button className="primary" type="button" onClick={() => dashRef.current?.openUpload()} disabled={dashImporting}>
      <Upload size={16} />
      {dashImporting ? "Uploading..." : "Upload CSV"}
    </button>
  );
}

function FeedbackActions({ feedbackRef, feedbackImporting }) {
  return (
    <>
      <button className="ghost" type="button" onClick={() => feedbackRef.current?.downloadTemplate()}>
        <Download size={16} />
        Download template
      </button>
      <button className="ghost" type="button" onClick={() => feedbackRef.current?.openUpload()} disabled={feedbackImporting}>
        <Upload size={16} />
        {feedbackImporting ? "Importing..." : "Import CSV"}
      </button>
      <button className="primary" type="button" onClick={() => feedbackRef.current?.openNew()}>
        <Plus size={16} />
        New feedback
      </button>
    </>
  );
}

function FilesActions({ filesRef }) {
  return (
    <button className="primary" type="button" onClick={() => filesRef.current?.openUpload()}>
      <Upload size={16} />
      Upload file
    </button>
  );
}

function SopsActions({ sopsRef }) {
  return (
    <button className="primary" type="button" onClick={() => sopsRef.current?.openNew()}>
      <Plus size={16} />
      New SOP
    </button>
  );
}

function AskActions({ askRef, askReindexing }) {
  return (
    <button className="ghost" type="button" onClick={() => askRef.current?.reindex()} disabled={askReindexing}>
      <RefreshCw size={16} />
      {askReindexing ? "Rebuilding..." : "Rebuild index"}
    </button>
  );
}

export const TOOLS = [
  {
    id: "leave",
    label: "Leave Forecast",
    title: "Leave Forecast",
    layer: "Leave tool",
    icon: CalendarDays,
    Workspace: LeaveForecast,
  },
  {
    id: "dashboard",
    label: "Dashboard",
    title: "Dashboard",
    layer: "Ops tool",
    icon: LayoutDashboard,
    Workspace: Dashboard,
    Actions: DashboardActions,
  },
  {
    id: "records",
    label: "Auto Rating Search",
    title: "AutoRatingSearchBar",
    layer: "Search tool",
    icon: FileText,
    Workspace: RecordsWorkspace,
    Actions: SearchActions,
  },
  {
    id: "feedback",
    label: "Feedback",
    title: "Feedback",
    layer: "Case tool",
    icon: Inbox,
    Workspace: FeedbackWorkspace,
    Actions: FeedbackActions,
  },
  {
    id: "files",
    label: "Files",
    title: "Files",
    layer: "Library tool",
    icon: FolderOpen,
    Workspace: FileManager,
    Actions: FilesActions,
  },
  {
    id: "sops",
    label: "SOPs",
    title: "SOPs",
    layer: "Process tool",
    icon: ClipboardList,
    Workspace: SopWorkspace,
    Actions: SopsActions,
  },
  {
    id: "ask",
    label: "Ask",
    title: "Ask",
    layer: "Knowledge tool",
    icon: MessageCircle,
    Workspace: AskWorkspace,
    Actions: AskActions,
  },
  {
    id: "logs",
    label: "Activity log",
    title: "Activity log",
    layer: "Audit tool",
    icon: ScrollText,
    Workspace: ActivityLog,
  },
];

export const TOOL_BY_ID = Object.fromEntries(TOOLS.map((tool) => [tool.id, tool]));
