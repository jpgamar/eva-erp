import { redirect } from "next/navigation";

// The Eva Customers module was consolidated into Empresas in the company
// CRM consolidation plan. Every visit to /eva-customers redirects to the
// accounts view inside Empresas, which now owns the linked-account UI,
// drafts, and the platform dashboard cards.
export default function EvaCustomersRedirect() {
  redirect("/empresas?view=accounts");
}
