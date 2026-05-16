import Hero from "./components/Hero";
import BullBearSplit from "./components/BullBearSplit";
import SplineSceneDemo from "./components/SplineSceneDemo";
import SplineChartsDemo from "./components/SplineChartsDemo";
import Footer from "./components/Footer";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col">
      <Hero />
      <BullBearSplit />
      <SplineSceneDemo />
      <SplineChartsDemo />
      <Footer />
    </main>
  );
}
