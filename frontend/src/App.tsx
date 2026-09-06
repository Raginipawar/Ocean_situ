import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Nav } from "./components/Nav";
import { Footer } from "./components/Footer";
import { Home } from "./pages/Home";

const DigitalTwin = lazy(() => import("./pages/DigitalTwin").then((m) => ({ default: m.DigitalTwin })));
const Services = lazy(() => import("./pages/Services").then((m) => ({ default: m.Services })));
const About = lazy(() => import("./pages/About").then((m) => ({ default: m.About })));
const Sitemap = lazy(() => import("./pages/Sitemap").then((m) => ({ default: m.Sitemap })));

function App() {
  return (
    <BrowserRouter>
      <Nav />
      <main>
        <Suspense fallback={<div className="px-6 py-32 text-center text-sm opacity-50">Loading...</div>}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/digital-twin" element={<DigitalTwin />} />
            <Route path="/services" element={<Services />} />
            <Route path="/about" element={<About />} />
            <Route path="/sitemap" element={<Sitemap />} />
          </Routes>
        </Suspense>
      </main>
      <Footer />
    </BrowserRouter>
  );
}

export default App;
