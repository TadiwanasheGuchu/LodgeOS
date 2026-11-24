"use client";

import { Check, Copy, Link2, MessageCircle, Plus, UserPlus, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field, Input, Select } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api-client";
import { formatDate } from "@/lib/format";
import type { Invitation, Member, RoleDefinition } from "@/lib/types";
import { cn } from "@/lib/utils";

type PropertyOption = { id: string; name: string };
type InvitationCreated = Invitation & { token: string };

const errorText = (err: unknown, fallback: string) => (err instanceof ApiError ? err.message : fallback);

export function TeamManager({
  members,
  roles,
  grantableRoleIds,
  invitations,
  properties,
  canManage,
  currentUserId,
  timeZone,
}: {
  members: Member[];
  roles: RoleDefinition[];
  grantableRoleIds: string[];
  invitations: Invitation[];
  properties: PropertyOption[];
  canManage: boolean;
  currentUserId: string;
  timeZone: string;
}) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [inviting, setInviting] = useState(false);
  const [link, setLink] = useState<{ name: string; url: string } | null>(null);
  const [addingTo, setAddingTo] = useState<Member | null>(null);
  const grantable = roles.filter((r) => grantableRoleIds.includes(r.id));

  async function run(key: string, fn: () => Promise<unknown>) {
    setBusy(key);
    setError(null);
    try {
      await fn();
      router.refresh();
    } catch (err) {
      setError(errorText(err, "Could not save the change."));
    } finally {
      setBusy(null);
    }
  }

  function showLink(created: InvitationCreated) {
    setLink({ name: created.full_name, url: `${window.location.origin}/invite/${created.token}` });
  }

  async function renew(inv: Invitation) {
    setBusy(inv.id);
    setError(null);
    try {
      const created = await api<InvitationCreated>("/api/v1/invitations", {
        method: "POST",
        body: { email: inv.email, full_name: inv.full_name, role_id: inv.role_id, property_id: inv.property_id },
      });
      showLink(created);
      router.refresh();
    } catch (err) {
      setError(errorText(err, "Could not create a new link."));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {canManage ? (
        <div>
          <Button onClick={() => setInviting(true)}>
            <UserPlus aria-hidden />
            Invite someone
          </Button>
        </div>
      ) : null}

      {error ? <Alert tone="error">{error}</Alert> : null}

      {invitations.length ? (
        <section aria-labelledby="invites-heading">
          <h2 id="invites-heading" className="mb-2 text-sm font-semibold text-forest">
            Invitations not yet accepted
          </h2>
          <ul className="divide-y divide-line rounded-lg border border-line bg-white">
            {invitations.map((inv) => (
              <li key={inv.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-forest">{inv.full_name}</p>
                  <p className="truncate text-sm text-muted">
                    {inv.email} · {inv.role_name}
                    {inv.property_name ? ` at ${inv.property_name}` : ""}
                  </p>
                </div>
                <span className={cn("text-[13px]", inv.state === "expired" ? "text-danger" : "text-muted")}>
                  {inv.state === "expired" ? "Link expired" : `Link valid until ${formatDate(inv.expires_at, timeZone)}`}
                </span>
                {canManage ? (
                  <div className="flex gap-1">
                    <Button variant="secondary" size="sm" loading={busy === inv.id} onClick={() => renew(inv)}>
                      <Link2 aria-hidden />
                      New link
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={busy !== null}
                      onClick={() => run(`revoke-${inv.id}`, () => api(`/api/v1/invitations/${inv.id}/revoke`, { method: "POST" }))}
                    >
                      Withdraw
                    </Button>
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section aria-labelledby="members-heading">
        <h2 id="members-heading" className="mb-2 text-sm font-semibold text-forest">
          {members.length} {members.length === 1 ? "person" : "people"}
        </h2>
        <ul className="divide-y divide-line rounded-lg border border-line bg-white">
          {members.map((m) => {
            const isMe = m.user_id === currentUserId;
            const disabled = m.status === "disabled";
            return (
              <li key={m.id} className={cn("flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-start", disabled && "bg-cloud")}>
                <div className="min-w-0 sm:w-64">
                  <p className={cn("font-medium", disabled ? "text-muted" : "text-forest")}>
                    {m.full_name}
                    {isMe ? <span className="ml-1.5 text-[13px] font-normal text-muted">(you)</span> : null}
                  </p>
                  <p className="truncate text-sm text-muted">{m.email}</p>
                  {disabled ? <p className="mt-1 text-[13px] font-medium text-danger">Access turned off</p> : null}
                </div>
                <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5">
                  {m.assignments.length === 0 ? <span className="text-sm text-muted">No roles</span> : null}
                  {m.assignments.map((a) => {
                    const removable = canManage && grantableRoleIds.includes(a.role_id);
                    const label = `${a.role_name} · ${a.property_name ?? "All properties"}`;
                    return (
                      <span
                        key={a.id}
                        className="inline-flex items-center gap-1 rounded-sm bg-mist py-0.5 pr-1 pl-2 text-[13px] text-forest"
                      >
                        {label}
                        {removable ? (
                          <button
                            type="button"
                            aria-label={`Remove ${label} from ${m.full_name}`}
                            disabled={busy !== null}
                            onClick={() =>
                              run(`rm-${a.id}`, () => api(`/api/v1/members/${m.id}/roles/${a.id}`, { method: "DELETE" }))
                            }
                            className="flex size-6 items-center justify-center rounded-sm hover:bg-white disabled:opacity-50"
                          >
                            <X className="size-3.5" aria-hidden />
                          </button>
                        ) : (
                          <span className="w-1" />
                        )}
                      </span>
                    );
                  })}
                  {canManage && grantable.length ? (
                    <Button variant="ghost" size="sm" onClick={() => setAddingTo(m)} aria-label={`Add a role for ${m.full_name}`}>
                      <Plus aria-hidden />
                      Role
                    </Button>
                  ) : null}
                </div>
                {canManage && !isMe ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    loading={busy === `status-${m.id}`}
                    onClick={() =>
                      run(`status-${m.id}`, () =>
                        api(`/api/v1/members/${m.id}`, { method: "PATCH", body: { status: disabled ? "active" : "disabled" } }),
                      )
                    }
                  >
                    {disabled ? "Turn access on" : "Turn access off"}
                  </Button>
                ) : null}
              </li>
            );
          })}
        </ul>
      </section>

      {inviting ? (
        <InviteDialog
          roles={grantable}
          properties={properties}
          onClose={() => setInviting(false)}
          onCreated={(created) => {
            setInviting(false);
            showLink(created);
            router.refresh();
          }}
        />
      ) : null}
      {link ? <LinkDialog name={link.name} url={link.url} onClose={() => setLink(null)} /> : null}
      {addingTo ? (
        <AddRoleDialog
          member={addingTo}
          roles={grantable}
          properties={properties}
          onClose={() => setAddingTo(null)}
          onDone={() => {
            setAddingTo(null);
            router.refresh();
          }}
        />
      ) : null}
    </div>
  );
}

function RoleAndProperty({
  roles,
  properties,
  roleId,
  propertyId,
  onRole,
  onProperty,
}: {
  roles: RoleDefinition[];
  properties: PropertyOption[];
  roleId: string;
  propertyId: string;
  onRole: (v: string) => void;
  onProperty: (v: string) => void;
}) {
  const isOwner = roles.find((r) => r.id === roleId)?.key === "owner";
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field id="invite-role" label="Role">
        <Select id="invite-role" value={roleId} onChange={(e) => onRole(e.target.value)}>
          {roles.map((r) => (
            <option key={r.id} value={r.id}>{r.name}</option>
          ))}
        </Select>
      </Field>
      <Field id="invite-property" label="Where" hint={isOwner ? "Owners always have every property." : undefined}>
        <Select
          id="invite-property"
          aria-describedby={isOwner ? "invite-property-hint" : undefined}
          value={isOwner ? "" : propertyId}
          disabled={isOwner}
          onChange={(e) => onProperty(e.target.value)}
        >
          <option value="">All properties</option>
          {properties.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </Select>
      </Field>
    </div>
  );
}

function InviteDialog({
  roles,
  properties,
  onClose,
  onCreated,
}: {
  roles: RoleDefinition[];
  properties: PropertyOption[];
  onClose: () => void;
  onCreated: (c: InvitationCreated) => void;
}) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [roleId, setRoleId] = useState(roles.find((r) => r.key === "receptionist")?.id ?? roles[0]?.id ?? "");
  const [propertyId, setPropertyId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (name.trim().length < 2) return setError("Enter their name.");
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) return setError("Enter a valid email address.");
    setBusy(true);
    setError(null);
    const isOwner = roles.find((r) => r.id === roleId)?.key === "owner";
    try {
      onCreated(
        await api<InvitationCreated>("/api/v1/invitations", {
          method: "POST",
          body: { full_name: name.trim(), email: email.trim(), role_id: roleId, property_id: isOwner ? null : propertyId || null },
        }),
      );
    } catch (err) {
      setError(errorText(err, "Could not create the invitation."));
      setBusy(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => (open ? null : onClose())}>
      <DialogContent title="Invite someone" description="You will get a link to send them. It works once and expires after 7 days.">
        <form method="post" onSubmit={submit} noValidate className="flex flex-col gap-4">
          {error ? <Alert tone="error">{error}</Alert> : null}
          <Field id="invite-name" label="Name">
            <Input id="invite-name" value={name} onChange={(e) => setName(e.target.value)} autoComplete="off" />
          </Field>
          <Field id="invite-email" label="Email" hint="They sign in with this address.">
            <Input
              id="invite-email"
              type="email"
              aria-describedby="invite-email-hint"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="off"
            />
          </Field>
          <RoleAndProperty roles={roles} properties={properties} roleId={roleId} propertyId={propertyId} onRole={setRoleId} onProperty={setPropertyId} />
          <div className="border-t border-line pt-4">
            <Button type="submit" loading={busy}>Create invitation link</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function LinkDialog({ name, url, onClose }: { name: string; url: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  const message = `You've been invited to LodgeOS. Open this link to set your password: ${url}`;

  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => (open ? null : onClose())}>
      <DialogContent title={`Send this link to ${name}`} description="This is the only time the link is shown. Anyone with it can join, so send it only to them.">
        <div className="flex flex-col gap-4">
          <Field id="invite-link" label="Invitation link">
            <Input id="invite-link" readOnly value={url} onFocus={(e) => e.currentTarget.select()} className="font-mono text-[13px]" />
          </Field>
          <div className="flex flex-wrap gap-2">
            <Button onClick={copy}>
              {copied ? <Check aria-hidden /> : <Copy aria-hidden />}
              {copied ? "Copied" : "Copy link"}
            </Button>
            <Button variant="secondary" asChild>
              <a href={`https://wa.me/?text=${encodeURIComponent(message)}`} target="_blank" rel="noopener noreferrer">
                <MessageCircle aria-hidden />
                Send on WhatsApp
              </a>
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function AddRoleDialog({
  member,
  roles,
  properties,
  onClose,
  onDone,
}: {
  member: Member;
  roles: RoleDefinition[];
  properties: PropertyOption[];
  onClose: () => void;
  onDone: () => void;
}) {
  const [roleId, setRoleId] = useState(roles[0]?.id ?? "");
  const [propertyId, setPropertyId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const isOwner = roles.find((r) => r.id === roleId)?.key === "owner";
    try {
      await api(`/api/v1/members/${member.id}/roles`, {
        method: "POST",
        body: { role_id: roleId, property_id: isOwner ? null : propertyId || null },
      });
      onDone();
    } catch (err) {
      setError(errorText(err, "Could not add the role."));
      setBusy(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => (open ? null : onClose())}>
      <DialogContent title={`Add a role for ${member.full_name}`}>
        <form method="post" onSubmit={submit} noValidate className="flex flex-col gap-4">
          {error ? <Alert tone="error">{error}</Alert> : null}
          <RoleAndProperty roles={roles} properties={properties} roleId={roleId} propertyId={propertyId} onRole={setRoleId} onProperty={setPropertyId} />
          <div className="border-t border-line pt-4">
            <Button type="submit" loading={busy}>Add role</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
