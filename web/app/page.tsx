import { connection } from "next/server";
import { Planner } from "@/components/Planner";
import { catalog, dataMode } from "@/lib/catalog.server";

export default async function Home() {
  await connection();
  return <Planner catalog={catalog} mode={dataMode()} />;
}
