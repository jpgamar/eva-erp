"use client";

import { useEffect, useState, useCallback } from "react";
import { usersApi } from "@/lib/api/users";
import { useAuth } from "@/lib/auth/context";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Plus, Shield, ShieldCheck, UserX, UserCheck, UsersRound } from "lucide-react";

interface TeamUser {
  id: string;
  email: string;
  name: string;
  role: string;
  avatar_url: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export default function TeamPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<TeamUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteName, setInviteName] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [inviting, setInviting] = useState(false);

  const fetchUsers = useCallback(async () => {
    try {
      const data = await usersApi.list();
      setUsers(data);
    } catch {
      toast.error("Failed to load team members");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setInviting(true);
    try {
      await usersApi.invite({ name: inviteName, email: inviteEmail, role: inviteRole });
      toast.success(`Invited ${inviteName}`);
      setInviteOpen(false);
      setInviteName("");
      setInviteEmail("");
      setInviteRole("member");
      await fetchUsers();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to invite user");
    } finally {
      setInviting(false);
    }
  };

  const handleToggleActive = async (u: TeamUser) => {
    if (u.id === currentUser?.id) {
      toast.error("You can't deactivate yourself");
      return;
    }
    try {
      if (u.is_active) {
        await usersApi.deactivate(u.id);
        toast.success(`${u.name} deactivated`);
      } else {
        await usersApi.update(u.id, { is_active: true });
        toast.success(`${u.name} reactivated`);
      }
      await fetchUsers();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to update user");
    }
  };

  const handleChangeRole = async (u: TeamUser, role: string) => {
    try {
      await usersApi.update(u.id, { role });
      toast.success(`${u.name} is now ${role}`);
      await fetchUsers();
    } catch {
      toast.error("Failed to change role");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-8rem)]">
        <div className="animate-spin h-8 w-8 border-4 border-accent border-t-transparent rounded-full" />
      </div>
    );
  }

  const activeUsers = users.filter(u => u.is_active);
  const inactiveUsers = users.filter(u => !u.is_active);

  return (
    <div className="space-y-6 animate-erp-entrance">
      {/* Stats + action */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-light">
            <UsersRound className="h-5 w-5 text-accent" />
          </div>
          <div>
            <p className="text-sm font-medium">{activeUsers.length} active member{activeUsers.length !== 1 ? "s" : ""}</p>
            {inactiveUsers.length > 0 && (
              <p className="text-xs text-muted-foreground">{inactiveUsers.length} deactivated</p>
            )}
          </div>
        </div>
        <Button size="sm" className="rounded-lg bg-accent hover:bg-accent/90 text-white" onClick={() => setInviteOpen(true)}>
          <Plus className="h-4 w-4 mr-2" /> Invite Member
        </Button>
      </div>

      {/* Active members table */}
      <div className="overflow-hidden rounded-xl border border-border bg-card">
        <Table>
          <TableHeader>
            <TableRow className="bg-gray-50/80">
              <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Member</TableHead>
              <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Email</TableHead>
              <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Role</TableHead>
              <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted text-right">Joined</TableHead>
              <TableHead className="w-[50px]" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {activeUsers.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-muted py-12">
                  No team members yet. Invite someone to get started.
                </TableCell>
              </TableRow>
            ) : activeUsers.map(u => (
              <TableRow key={u.id}>
                <TableCell>
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent-light text-accent font-semibold text-xs">
                      {u.name.split(" ").map(n => n[0]).join("").slice(0, 2).toUpperCase()}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">{u.name}</span>
                      {u.id === currentUser?.id && (
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0">You</Badge>
                      )}
                    </div>
                  </div>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">{u.email}</TableCell>
                <TableCell>
                  <Select
                    value={u.role}
                    onValueChange={(role) => handleChangeRole(u, role)}
                    disabled={u.id === currentUser?.id}
                  >
                    <SelectTrigger className="w-28 h-7 text-xs border-none bg-transparent shadow-none hover:bg-accent px-2">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="admin">
                        <span className="flex items-center gap-1.5"><ShieldCheck className="h-3 w-3" /> Admin</span>
                      </SelectItem>
                      <SelectItem value="member">
                        <span className="flex items-center gap-1.5"><Shield className="h-3 w-3" /> Member</span>
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </TableCell>
                <TableCell className="text-right text-sm text-muted-foreground">
                  {new Date(u.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                </TableCell>
                <TableCell>
                  {u.id !== currentUser?.id && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-muted-foreground hover:text-destructive"
                      onClick={() => handleToggleActive(u)}
                    >
                      <UserX className="h-4 w-4" />
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Deactivated section */}
      {inactiveUsers.length > 0 && (
        <>
          <h3 className="text-sm font-medium text-muted pt-2">Deactivated</h3>
          <div className="overflow-hidden rounded-xl border border-border bg-card opacity-70">
            <Table>
              <TableBody>
                {inactiveUsers.map(u => (
                  <TableRow key={u.id}>
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted text-muted-foreground font-semibold text-xs">
                          {u.name.split(" ").map(n => n[0]).join("").slice(0, 2).toUpperCase()}
                        </div>
                        <span className="font-medium text-sm">{u.name}</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">{u.email}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="outline" size="sm" onClick={() => handleToggleActive(u)}>
                        <UserCheck className="h-3.5 w-3.5 mr-1.5" /> Reactivate
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </>
      )}

      {/* Invite Dialog */}
      <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
        <DialogContent className="p-0">
          <div className="border-b border-border bg-gray-50/80 px-6 py-4">
            <h2 className="text-base font-semibold text-foreground">Invite Team Member</h2>
            <p className="text-xs text-muted">Add a new team member to your workspace</p>
          </div>
          <form onSubmit={handleInvite} className="space-y-4 px-6 py-4">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Name *</Label>
              <Input className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20" value={inviteName} onChange={(e) => setInviteName(e.target.value)} placeholder="Full name" required />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Email *</Label>
              <Input className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20" type="email" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} placeholder="user@goeva.ai" required />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Role</Label>
              <Select value={inviteRole} onValueChange={setInviteRole}>
                <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="member">Member</SelectItem>
                  <SelectItem value="admin">Admin</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" className="rounded-lg" onClick={() => setInviteOpen(false)}>Cancel</Button>
              <Button type="submit" className="rounded-lg bg-accent hover:bg-accent/90 text-white" disabled={inviting}>{inviting ? "Inviting..." : "Send Invite"}</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
