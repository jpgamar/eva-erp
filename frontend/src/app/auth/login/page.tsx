import { redirect } from "next/navigation";

export default function LegacyAuthLoginPage() {
  redirect("/login");
}
