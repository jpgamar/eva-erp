"use client";

import { Card, CardContent } from "@/components/ui/card";
import { OwlIcon } from "@/components/owl-icon";

export default function AssistantPage() {
  return (
    <div className="flex items-center justify-center h-[calc(100vh-8rem)]">
      <Card className="max-w-md w-full text-center py-16">
        <CardContent>
          <div className="mx-auto mb-6">
            <OwlIcon className="h-24 w-24 mx-auto" size="lg" />
          </div>
          <h2 className="text-2xl font-bold mb-2">Eva</h2>
          <p className="text-muted-foreground">Coming soon</p>
        </CardContent>
      </Card>
    </div>
  );
}
