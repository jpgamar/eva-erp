import { redirect } from "next/navigation";

// The Prospects module was unified into Empresas in the ERP Empresas Pipeline
// unification. Every visit to /prospects redirects to the Kanban filtered on
// the prospecto stage. The old 1,016-line page has been archived in git
// history and will be dropped in the follow-up PR that removes the
// prospects/ backend module.
export default function ProspectsPage() {
  redirect("/empresas?stage=prospecto");
}
