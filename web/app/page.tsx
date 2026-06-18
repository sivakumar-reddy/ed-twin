import EDConsole from "@/components/EDConsole";

export default function Home() {
  return (
    <main className="wrap">
      <div className="eyebrow">Emergency Department Digital Twin</div>
      <h1>
        The crowded ER doesn&apos;t need more <em>beds</em>.
      </h1>
      <p className="sub">
        It needs more physicians. Drag the levers and watch what actually moves
        the time a patient spends in the department. The numbers come from a
        simulation run thousands of times, not a guess.
      </p>
      <EDConsole />
    </main>
  );
}
