import React from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, LogOut } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useUser } from "@/context/UserContext";
import { useBackButton } from "@/hooks/useTelegramUI";
import { haptic } from "@/lib/platform";
import "@/pages/Profile.css";

const PROVIDER_LABEL = { telegram: "Telegram", email: "Email", google: "Google" };

export default function Profile() {
  const navigate = useNavigate();
  const { authUser, logout } = useAuth();
  const { avatarUrl, env, platform } = useUser();

  useBackButton(true, () => navigate(-1));

  const providers = (authUser && authUser.auth_provider) || [];

  const onLogout = async () => {
    haptic("medium");
    await logout();
    navigate("/");
  };

  const platformLabel =
    env === "telegram"
      ? `Telegram (${platform})`
      : env === "pwa"
      ? "Установленное приложение (PWA)"
      : "Веб-браузер";

  return (
    <div className="profile-page" data-testid="profile-page">
      <header className="profile-header">
        <button
          className="profile-back"
          onClick={() => navigate(-1)}
          aria-label="Назад"
          data-testid="profile-back"
        >
          <ArrowLeft size={22} />
        </button>
        <h1 className="profile-title">Профиль</h1>
      </header>

      <div className="profile-card">
        <img src={avatarUrl} alt="" className="profile-avatar-lg" />
        <div className="profile-name">{authUser?.first_name || "Пользователь"}</div>
        {authUser?.email ? (
          <div className="profile-email">{authUser.email}</div>
        ) : null}
        {authUser?.username ? (
          <div className="profile-username">@{authUser.username}</div>
        ) : null}
        {providers.length ? (
          <div className="profile-badges">
            {providers.map((p) => (
              <span key={p} className="profile-badge">
                {PROVIDER_LABEL[p] || p}
              </span>
            ))}
          </div>
        ) : null}
      </div>

      <div className="profile-meta">
        <div className="profile-meta-row">
          <span>Вход выполнен через</span>
          <b>{providers.map((p) => PROVIDER_LABEL[p] || p).join(", ") || "—"}</b>
        </div>
        <div className="profile-meta-row">
          <span>Платформа</span>
          <b>{platformLabel}</b>
        </div>
      </div>

      <button className="profile-logout" onClick={onLogout} data-testid="logout-btn">
        <LogOut size={18} /> Выйти
      </button>
    </div>
  );
}
