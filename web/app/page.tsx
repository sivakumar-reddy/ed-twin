import EDConsole from "../components/EDConsole";

export const metadata = {
  title: "Emergency Department Digital Twin",
  description:
    "A discrete event simulation calibrated on 424,725 real MIMIC-IV-ED visits. Interactive evidence that inpatient capacity, not physicians or ED beds, is the binding constraint on length of stay.",
};

export default function Page() {
  return <EDConsole />;
}
