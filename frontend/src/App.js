import "@/App.css";
import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Link, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { UserProvider, useUser } from "@/context/UserContext";
import { getStats } from "@/api";
import DateSelector from "@/components/DateSelector";
import Programs from "@/pages/Programs";
import Login from "@/pages/Login";
import Profile from "@/pages/Profile";
import InstallPrompt from "@/components/InstallPrompt";

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
  const [streak, setStreak] = useState(0);

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
          
          {/* Training Streak */}
          <div className="streak-row" data-testid="streak-row">
            <img 
              src="/fire_strike.svg" 
              alt="" 
              className="streak-icon"
              data-testid="streak-icon"
            />
            <span className="streak-text" data-testid="streak-text">
              Тренировочная серия в течение {streak} {pluralize(streak, ['дня', 'дней', 'дней'])}
            </span>
          </div>
          
          {/* Date Selector */}
          <DateSelector />
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

const AppShell = () => {
  const { loading, isAuthenticated } = useAuth();
  if (loading) return <SplashScreen />;
  if (!isAuthenticated) return <Login />;
  return (
    <UserProvider>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/programs" element={<Programs />} />
        <Route path="/profile" element={<Profile />} />
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
          <InstallPrompt />
          <AppShell />
        </BrowserRouter>
      </AuthProvider>
    </div>
  );
}

export default App;
