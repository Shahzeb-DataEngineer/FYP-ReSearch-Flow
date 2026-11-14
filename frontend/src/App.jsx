import {Routes, Route} from "react-router-dom";
import Home from './pages/Home';
import AuthPage from './pages/AuthPage';
import MainLayout from './layouts/MainLayout';
import AuthLayout from './layouts/AuthLayout';
import AuthCallback from './pages/AuthCallBack';
import Results from './pages/Results';
import PrismaReview from './pages/PrismaReview';
import CitationGraph from './pages/CitationGraph';
import MyLibrary from './pages/MyLibrary';
import SavedSearches from './pages/SavedSearches';
import Pricing from './pages/Pricing';
import Payment from './pages/Payment';


function App() {

  return (
    <>
      <Routes>
        {/* Pages with Navbar */}
        <Route element={<MainLayout />}>
          <Route path="/" element={<Home />} />
          <Route path="/results" element={<Results />} />
          <Route path="/prisma" element={<PrismaReview />} />
          <Route path="/citation-graph" element={<CitationGraph />} />
          <Route path="/my-library" element={<MyLibrary />} />
          <Route path="/saved-searches" element={<SavedSearches />} />
          <Route path="/pricing" element={<Pricing />} />
          <Route path="/payment" element={<Payment />} />
        </Route>
        
        {/* Auth pages without Navbar */}
        <Route element={<AuthLayout />}>
          <Route path="/auth" element={<AuthPage />} />
          <Route path="/auth/callback" element={<AuthCallback />} />
        </Route>
      </Routes>
    
    </>
  )
}

export default App
