"use client";

import { useState, FormEvent } from "react";
import { useAuth } from "../../../lib/auth-context";
import { apiFetch, type ApiError } from "../../../lib/api";
import { useToast } from "../../../components/Toast";

export default function ProfilePage() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [firstName, setFirstName] = useState(user?.first_name || "");
  const [lastName, setLastName] = useState(user?.last_name || "");
  const [saving, setSaving] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [changingPw, setChangingPw] = useState(false);

  async function handleSaveProfile(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await apiFetch("/auth/profile", {
        method: "PATCH",
        body: JSON.stringify({ first_name: firstName, last_name: lastName }),
      });
      showToast("Profile updated", "success");
    } catch (e) {
      const err = e as ApiError;
      showToast(err.message || "Failed to update", "error");
    }
    setSaving(false);
  }

  async function handleChangePassword(e: FormEvent) {
    e.preventDefault();
    setChangingPw(true);
    try {
      await apiFetch("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      showToast("Password changed", "success");
      setCurrentPassword("");
      setNewPassword("");
    } catch (e) {
      const err = e as ApiError;
      showToast(err.message || "Failed to change password", "error");
    }
    setChangingPw(false);
  }

  return (
    <div>
      <h1 className="font-serif text-2xl font-bold mb-6">
        <span className="gradient-text">Profile</span>
      </h1>

      {/* Profile form */}
      <form onSubmit={handleSaveProfile} className="glass rounded-xl p-6 mb-6">
        <h2 className="text-lg font-semibold text-text-primary mb-4">Personal Info</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-text-secondary mb-1">Email</label>
            <input value={user?.email || ""} disabled className="input-glass text-sm opacity-50" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm text-text-secondary mb-1">First name</label>
              <input value={firstName} onChange={(e) => setFirstName(e.target.value)} className="input-glass text-sm" />
            </div>
            <div>
              <label className="block text-sm text-text-secondary mb-1">Last name</label>
              <input value={lastName} onChange={(e) => setLastName(e.target.value)} className="input-glass text-sm" />
            </div>
          </div>
          <button type="submit" disabled={saving} className="btn-primary text-sm disabled:opacity-50">
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </form>

      {/* Change password */}
      <form onSubmit={handleChangePassword} className="glass rounded-xl p-6">
        <h2 className="text-lg font-semibold text-text-primary mb-4">Change Password</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-text-secondary mb-1">Current password</label>
            <input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} required className="input-glass text-sm" />
          </div>
          <div>
            <label className="block text-sm text-text-secondary mb-1">New password</label>
            <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required minLength={8} className="input-glass text-sm" />
            <p className="text-xs text-text-muted mt-1">Min 8 characters with uppercase, lowercase, and digit</p>
          </div>
          <button type="submit" disabled={changingPw} className="btn-secondary text-sm disabled:opacity-50">
            {changingPw ? "Changing..." : "Change Password"}
          </button>
        </div>
      </form>
    </div>
  );
}
