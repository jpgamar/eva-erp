import { redirect } from "next/navigation";

export default function EvaCustomersRedirect() {
  redirect("/empresas?view=accounts");
}
