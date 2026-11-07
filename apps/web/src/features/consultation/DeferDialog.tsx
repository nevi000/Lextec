import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogTitle } from "@/components/ui/dialog";
import { FieldError, Label, Textarea } from "@/components/ui/input";
import { api } from "@/lib/api";
import { errorMessage, useInvalidateCase } from "@/lib/queries";

const schema = z.object({ reason: z.string().trim().min(3, "Bitte einen kurzen Grund angeben (mind. 3 Zeichen).").max(500) });

export function DeferDialog({
  caseId,
  factId,
  label,
  open,
  onOpenChange,
}: {
  caseId: string;
  factId: string | null;
  label: string;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const invalidate = useInvalidateCase(caseId);
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { reason: "" } });
  const mutation = useMutation({
    mutationFn: (reason: string) => api.deferFact(caseId, factId ?? "", reason),
    onSuccess: () => {
      void invalidate();
      toast.success("Frage zurückgestellt. Die Angabe bleibt offen.");
      form.reset();
      onOpenChange(false);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>Frage zurückstellen</DialogTitle>
        <DialogDescription>
          «{label}» bleibt offen und blockiert weiterhin eine abschliessende Einschätzung. Die Frage wird später erneut
          vorgeschlagen.
        </DialogDescription>
        <form className="mt-4" onSubmit={form.handleSubmit((v) => mutation.mutate(v.reason))}>
          <Label htmlFor="defer-reason">Grund für die Zurückstellung</Label>
          <Textarea
            id="defer-reason"
            rows={3}
            placeholder="z. B. Unterlagen liegen heute nicht vor"
            aria-invalid={!!form.formState.errors.reason || undefined}
            {...form.register("reason")}
          />
          <FieldError>{form.formState.errors.reason?.message}</FieldError>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Abbrechen
            </Button>
            <Button type="submit" loading={mutation.isPending}>
              Zurückstellen
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
