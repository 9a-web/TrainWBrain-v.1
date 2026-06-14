import "@/App.css";
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import { Toaster } from "sonner";
import { UserProvider, useUser } from "@/context/UserContext";
import DateSelector from "@/components/DateSelector";
import Programs from "@/pages/Programs";

const Home = () => {
  const { user } = useUser();

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
          
          {/* Right side: Menu */}
          <div className="header-right" data-testid="header-right">
            <Link
              to="/programs"
              className="menu-button"
              data-testid="menu-button"
              aria-label="Программы"
            >
              <img src="/menu.svg" alt="Программы" width={40} height={40} />
            </Link>
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
              Тренировочная серия в течение 0 дней
            </span>
          </div>
          
          {/* Date Selector */}
          <DateSelector />
        </main>
      </div>
    </div>
  );
};

function App() {
  return (
    <div className="App">
      <UserProvider>
        <BrowserRouter>
          <Toaster position="top-center" theme="dark" richColors />
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/programs" element={<Programs />} />
          </Routes>
        </BrowserRouter>
      </UserProvider>
    </div>
  );
}

export default App;
