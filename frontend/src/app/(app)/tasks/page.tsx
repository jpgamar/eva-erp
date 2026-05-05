import { redirect } from "next/navigation";

// /tasks was consolidated into /empresas?view=tasks in the
// empresas-ux-pass. The redirect keeps any bookmarked URL working.
export default function TasksRedirect() {
  redirect("/empresas?view=tasks");
}
