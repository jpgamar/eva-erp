"use client";

import { useEffect, useState } from "react";
import { Plus, Folder as FolderIcon, FileText, Search, Upload, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { foldersApi, documentsApi } from "@/lib/api/documents";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";

interface FolderEntry { id: string; name: string; parent_id: string | null; position: number; created_at: string; }
interface DocEntry { id: string; name: string; folder_id: string; file_url: string; file_size: number; mime_type: string; description: string | null; tags: string[] | null; created_at: string; }

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DocumentsPage() {
  const [folders, setFolders] = useState<FolderEntry[]>([]);
  const [documents, setDocuments] = useState<DocEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentFolder, setCurrentFolder] = useState<string | null>(null);
  const [folderName, setFolderName] = useState("");
  const [addFolderOpen, setAddFolderOpen] = useState(false);
  const [search, setSearch] = useState("");

  const fetchData = async () => {
    try {
      const [fList, dList] = await Promise.all([
        foldersApi.list(currentFolder || undefined),
        documentsApi.list({ folder_id: currentFolder || undefined, search: search || undefined }),
      ]);
      setFolders(fList);
      setDocuments(dList);
    } catch { toast.error("Failed to load"); } finally { setLoading(false); }
  };

  useEffect(() => { fetchData(); }, [currentFolder, search]);

  const handleCreateFolder = async () => {
    try {
      await foldersApi.create({ name: folderName, parent_id: currentFolder || undefined });
      toast.success("Folder created");
      setAddFolderOpen(false);
      setFolderName("");
      await fetchData();
    } catch (e: any) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !currentFolder) {
      toast.error("Select a folder first");
      return;
    }
    const formData = new FormData();
    formData.append("file", file);
    formData.append("folder_id", currentFolder);
    formData.append("name", file.name);
    try {
      await documentsApi.upload(formData);
      toast.success("File uploaded");
      await fetchData();
    } catch { toast.error("Upload failed"); }
    e.target.value = "";
  };

  const handleDeleteDoc = async (id: string) => {
    try {
      await documentsApi.delete(id);
      toast.success("Deleted");
      await fetchData();
    } catch { toast.error("Failed"); }
  };

  if (loading) return <div className="flex items-center justify-center h-[calc(100vh-8rem)]"><div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" /></div>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-bold">Documents</h1><p className="text-muted-foreground text-sm">Contracts, legal, brand assets</p></div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => setAddFolderOpen(true)}><Plus className="h-4 w-4 mr-1" /> Folder</Button>
          <label>
            <Button size="sm" asChild><span><Upload className="h-4 w-4 mr-1" /> Upload</span></Button>
            <input type="file" className="hidden" onChange={handleUpload} />
          </label>
        </div>
      </div>

      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm">
        <button onClick={() => setCurrentFolder(null)} className="text-primary hover:underline">Root</button>
        {currentFolder && <span className="text-muted-foreground">/ (subfolder)</span>}
      </div>

      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input placeholder="Search files..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9" />
      </div>

      {/* Folders */}
      {folders.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-muted-foreground mb-2">Folders</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            {folders.map((f) => (
              <Card key={f.id} className="cursor-pointer hover:border-primary/50 transition-colors" onClick={() => setCurrentFolder(f.id)}>
                <CardContent className="pt-4 pb-4 flex items-center gap-2">
                  <FolderIcon className="h-5 w-5 text-primary shrink-0" />
                  <span className="text-sm font-medium truncate">{f.name}</span>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Documents */}
      <div>
        <h3 className="text-sm font-semibold text-muted-foreground mb-2">Files</h3>
        {documents.length === 0 ? (
          <Card className="text-center py-8"><CardContent><p className="text-muted-foreground">{currentFolder ? "No files in this folder." : "Select a folder or upload files."}</p></CardContent></Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {documents.map((doc) => (
              <Card key={doc.id}>
                <CardContent className="pt-4 pb-4">
                  <div className="flex items-start gap-3">
                    <FileText className="h-8 w-8 text-muted-foreground shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{doc.name}</p>
                      <p className="text-xs text-muted-foreground">{formatSize(doc.file_size)} &middot; {doc.mime_type}</p>
                      {doc.tags && doc.tags.length > 0 && (
                        <div className="flex gap-1 mt-1">{doc.tags.map(t => <Badge key={t} variant="secondary" className="text-xs">{t}</Badge>)}</div>
                      )}
                    </div>
                    <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0" onClick={() => handleDeleteDoc(doc.id)}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Add Folder Dialog */}
      <Dialog open={addFolderOpen} onOpenChange={setAddFolderOpen}>
        <DialogContent><DialogHeader><DialogTitle>New Folder</DialogTitle></DialogHeader>
          <form onSubmit={(e) => { e.preventDefault(); handleCreateFolder(); }} className="space-y-3">
            <div><Label>Folder Name *</Label><Input value={folderName} onChange={(e) => setFolderName(e.target.value)} required autoFocus /></div>
            <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setAddFolderOpen(false)}>Cancel</Button><Button type="submit">Create</Button></div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
