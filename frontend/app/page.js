import Hero from "./components/Hero";
import BullBearSplit from "./components/BullBearSplit";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col">
      <Hero />
      <BullBearSplit />
    </main>
  );
}
