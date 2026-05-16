import Hero from "./components/Hero";
import BullBearSplit from "./components/BullBearSplit";
import SplineSceneDemo from "./components/SplineSceneDemo";
import SampleDisputedFact from "./components/SampleDisputedFact";
import SplineChartsDemo from "./components/SplineChartsDemo";
import Footer from "./components/Footer";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col">
      <Hero />
      <BullBearSplit />
      <SplineSceneDemo />
      <SampleDisputedFact />
      <SplineChartsDemo />
      <Footer />
    </main>
  );
}
