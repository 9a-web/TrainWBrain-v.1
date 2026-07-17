import "@/App.css";
import { useEffect, useState, useRef } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Link,
  Navigate,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { UserProvider, useUser } from "@/context/UserContext";
import { getStats } from "@/api";
import DateSelector from "@/components/DateSelector";
import DiaryHome from "@/components/DiaryHome";
import Programs from "@/pages/Programs";
import ProgramBuilder from "@/pages/ProgramBuilder";
import AiImport from "@/pages/AiImport";
import ImportLanding from "@/pages/ImportLanding";
import Login from "@/pages/Login";
import { getStartParam } from "@/lib/platform";
import Profile from "@/pages/Profile";
import Coach from "@/pages/Coach";
import CoachClient from "@/pages/CoachClient";
import CoachPlanEditor from "@/pages/CoachPlanEditor";
import CoachLiveSession from "@/pages/CoachLiveSession";
import { StatsPage, CoachClientStatsPage } from "@/pages/Stats";
import StreakPage from "@/pages/Streak";
import { ChevronRight } from "lucide-react";

const pluralize = (n, forms) => {
  const a = Math.abs(n) % 100;
  const b = a % 10;
  if (a > 10 && a < 20) return forms[2];
  if (b > 1 && b < 5) return forms[1];
  if (b === 1) return forms[0];
  return forms[2];
};

const Home = () => {
  const { user, avatarUrl } = useUser();
  const navigate = useNavigate();
  const [streak, setStreak] = useState(0);
  const [homeMode, setHomeMode] = useState(
    () => (typeof window !== "undefined" && window.localStorage.getItem("twb_home_mode")) || "plan"
  );
  const switchHomeMode = (m) => {
    setHomeMode(m);
    try {
      window.localStorage.setItem("twb_home_mode", m);
    } catch (e) {
      /* no-op */
    }
  };

  useEffect(() => {
    if (!user?.telegram_id) return undefined;
    let cancelled = false;
    const load = async () => {
      try {
        const s = await getStats(user.telegram_id);
        if (!cancelled) setStreak(s?.streak_days || 0);
      } catch (e) {
        /* no-op */
      }
    };
    load();
    const onProgress = () => load();
    window.addEventListener("twb:progress", onProgress);
    return () => {
      cancelled = true;
      window.removeEventListener("twb:progress", onProgress);
    };
  }, [user?.telegram_id]);

  // Get greeting and icon based on current time
  const getGreetingData = () => {
    const hour = new Date().getHours();
    if (hour >= 5 && hour < 12) {
      return { text: 'Доброе утро', icon: '/sunrise.svg' };
    } else if (hour >= 12 && hour < 18) {
      return { text: 'Добрый день', icon: '/day.svg' };
    } else if (hour >= 18 && hour < 23) {
      return { text: 'Добрый вечер', icon: '/sunset.svg' };
    } else {
      return { text: 'Доброй ночи', icon: '/night.svg' };
    }
  };

  const greetingData = getGreetingData();

  return (
    <div className="app-container" data-testid="main-container">
      {/* Gradient Background with Blur Effect */}
      <div className="gradient-background" data-testid="gradient-background">
        <img 
          src="/gradientcenter.png" 
          alt="" 
          aria-hidden="true"
        />
      </div>
      
      {/* Content Layer */}
      <div className="content-layer" data-testid="content-layer">
        {/* Header */}
        <header className="header" data-testid="header">
          {/* Logo */}
          <div className="header-logo" data-testid="header-logo">
            <img src="/TWBlogo.png" alt="TrainWithBrain" />
          </div>
          
          {/* Right side: Menu + Avatar */}
          <div className="header-right" data-testid="header-right">
            <Link
              to="/programs"
              className="menu-button"
              data-testid="menu-button"
              aria-label="Программы"
            >
              <img src="/menu.svg" alt="Программы" width={40} height={40} />
            </Link>
            {avatarUrl ? (
              <Link to="/profile" aria-label="Профиль" data-testid="profile-link">
                <img
                  src={avatarUrl}
                  alt="Профиль"
                  className="profile-avatar"
                  data-testid="profile-avatar"
                />
              </Link>
            ) : null}
          </div>
        </header>
        
        {/* Main Content Area - Greeting */}
        <main className="main-content" data-testid="main-content">
          <div className="greeting-row" data-testid="greeting-row">
            <h1 className="greeting-text" data-testid="greeting-text">
              {greetingData.text}, {user?.first_name || 'Гость'}!
            </h1>
            <img 
              src={greetingData.icon} 
              alt="" 
              className="greeting-icon"
              data-testid="greeting-icon"
            />
          </div>
          
          {/* Training Streak — ведёт к экрану тренировочной серии */}
          <button
            type="button"
            className="streak-row streak-row-link"
            data-testid="streak-row"
            onClick={() => navigate("/streak")}
            aria-label="Открыть тренировочную серию"
          >
            <img 
              src="/fire_strike.svg" 
              alt="" 
              className="streak-icon"
              data-testid="streak-icon"
            />
            <span className="streak-text" data-testid="streak-text">
              Тренировочная серия в течение {streak} {pluralize(streak, ['дня', 'дней', 'дней'])}
            </span>
            <ChevronRight size={18} className="streak-chevron" aria-hidden="true" />
          </button>
          
          {/* Toggle: План / Дневник (тумблер режима на главном экране) */}
          <div className="home-mode-toggle" data-testid="home-mode-toggle">
            <button
              className={homeMode === "plan" ? "active" : ""}
              onClick={() => switchHomeMode("plan")}
              data-testid="home-mode-plan"
            >
              План
            </button>
            <button
              className={homeMode === "diary" ? "active" : ""}
              onClick={() => switchHomeMode("diary")}
              data-testid="home-mode-diary"
            >
              Дневник
            </button>
          </div>

          {/* Контент режима */}
          {homeMode === "diary" ? <DiaryHome /> : <DateSelector />}
        </main>
      </div>
    </div>
  );
};

const SplashScreen = () => (
  <div className="app-splash" data-testid="app-splash">
    <img src="/TWBlogo.png" alt="TrainWithBrain" className="app-splash-logo" />
  </div>
);

// Handles the Google OAuth redirect back to <origin>/auth/google?code=...
const GoogleCallback = () => {
  const { handleGoogleCode } = useAuth();
  const navigate = useNavigate();
  const ranRef = useRef(false);
  useEffect(() => {
    if (ranRef.current) return;
    ranRef.current = true;
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    (async () => {
      if (code) {
        try {
          await handleGoogleCode(code);
        } catch (e) {
          /* ignore — fall back to login */
        }
      }
      navigate("/", { replace: true });
    })();
  }, [handleGoogleCode, navigate]);
  return <SplashScreen />;
};

const AppShell = () => {
  const { loading, isAuthenticated } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const importHandledRef = useRef(false);

  // Отложенный импорт по ссылке/коду: после логина или из Telegram start_param
  useEffect(() => {
    if (!isAuthenticated || importHandledRef.current) return;
    let code = null;
    try {
      code = window.localStorage.getItem("twb_pending_import");
    } catch (e) {
      /* no-op */
    }
    if (!code) {
      const sp = getStartParam();
      if (sp && sp.startsWith("import_")) code = sp.slice(7).replace(/_/g, "-");
    }
    if (code) {
      importHandledRef.current = true;
      try {
        window.localStorage.removeItem("twb_pending_import");
      } catch (e) {
        /* no-op */
      }
      navigate(`/import/${code}`);
    }
  }, [isAuthenticated, navigate]);

  if (location.pathname === "/auth/google") return <GoogleCallback />;
  if (loading) return <SplashScreen />;
  if (!isAuthenticated) {
    // Публичная landing-страница импорта доступна без входа
    if (location.pathname.startsWith("/import/")) return <ImportLanding />;
    return <Login />;
  }
  return (
    <UserProvider>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/programs" element={<Programs />} />
        <Route path="/programs/builder/:templateId" element={<ProgramBuilder />} />
        <Route path="/programs/ai" element={<AiImport />} />
        <Route path="/import/:code" element={<ImportLanding />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/stats" element={<StatsPage />} />
        <Route path="/streak" element={<StreakPage />} />
        <Route path="/coach" element={<Coach />} />
        <Route path="/coach/:athleteId" element={<CoachClient />} />
        <Route path="/coach/:athleteId/live" element={<CoachLiveSession />} />
        <Route path="/coach/:athleteId/edit" element={<CoachPlanEditor />} />
        <Route path="/coach/:athleteId/stats" element={<CoachClientStatsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </UserProvider>
  );
};

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Toaster position="top-center" theme="dark" richColors />
          <AppShell />
        </BrowserRouter>
      </AuthProvider>
    </div>
  );
}

export default App;
