import { Construction } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

export function ComingSoon({ title }: { title: string }) {
  return (
    <div className="flex items-center justify-center h-[calc(100vh-8rem)]">
      <Card className="max-w-md w-full text-center">
        <CardContent className="pt-8 pb-8 space-y-4">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
            <Construction className="h-8 w-8 text-primary" />
          </div>
          <h2 className="text-2xl font-semibold">{title}</h2>
          <p className="text-muted-foreground">
            This module is coming soon. We&apos;re building it right now.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
