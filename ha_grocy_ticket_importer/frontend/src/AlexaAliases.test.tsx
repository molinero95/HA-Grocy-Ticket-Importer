import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { AlexaAliases } from "./AlexaAliases";
import * as api from "./api";
import { deferred, renderWithClient } from "./test/helpers";
vi.mock("./api", () => ({ getInventory: vi.fn(), getAlexaAliases: vi.fn(), saveAlexaAlias: vi.fn(), updateAlexaAlias: vi.fn(), deleteAlexaAlias: vi.fn() }));
const item = (id: number, name: string) => ({ id, name, amount: "0", unit: "Piece", image_url: null, shopping_amount: "0", shopping_step: "1", shopping_unit: "Piece", shopping_can_subtract: false });
const aliases = [{ key: "leche", name: "Leche", product_id: 7 }, { key: "bebida blanca", name: "Bebida blanca", product_id: 7 }, { key: "rojo", name: "Rojo", product_id: 8 }];
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.getInventory).mockResolvedValue({ items: [item(7, "Leche entera"), item(8, "Tomáte")] });
  vi.mocked(api.getAlexaAliases).mockResolvedValue({ aliases, suggestions: ["Leche normal", "Pan"] });
});
it("lists all editable aliases immediately and deletes only the reviewed identity", async () => {
  vi.mocked(api.deleteAlexaAlias).mockResolvedValue({});
  renderWithClient(<AlexaAliases />);
  expect(await screen.findByLabelText("Alias: Leche")).toHaveProperty("value", "Leche");
  expect(screen.getByLabelText("Alias: Rojo")).toBeTruthy();
  await userEvent.click(screen.getByRole("button", { name: "Eliminar alias Leche" }));
  expect(api.deleteAlexaAlias).toHaveBeenCalledExactlyOnceWith("leche", 7);
});
it("searches alias and product without accents/case and retains hidden drafts", async () => {
  renderWithClient(<AlexaAliases />);
  const milk = await screen.findByLabelText("Alias: Leche");
  await userEvent.selectOptions(milk, "__write_alias__");
  await userEvent.type(screen.getByLabelText("Escribir alias: leche"), " normal");
  const search = screen.getByRole("searchbox", { name: "Buscar alias o producto" });
  await userEvent.type(search, "TOMATE");
  expect(screen.getByLabelText("Alias: Rojo")).toBeTruthy();
  expect(screen.queryByRole("combobox", { name: "Alias: Leche" })).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Borrar búsqueda de alias" }));
  expect(screen.getByLabelText("Escribir alias: leche")).toHaveProperty("value", "Leche normal");
  await userEvent.type(search, "BEBIDA");
  expect(screen.getByLabelText("Alias: Bebida blanca")).toBeTruthy();
  expect(screen.queryByRole("combobox", { name: "Alias: Rojo" })).toBeNull();
});
it("atomically saves both edited fields with the original expected identity, once", async () => {
  const pending = deferred<Awaited<ReturnType<typeof api.updateAlexaAlias>>>();
  vi.mocked(api.updateAlexaAlias).mockReturnValue(pending.promise);
  renderWithClient(<AlexaAliases />);
  const input = await screen.findByLabelText("Alias: Leche");
  await userEvent.selectOptions(input, "Leche normal");
  await userEvent.selectOptions(screen.getByLabelText("Producto para Leche"), "8");
  await userEvent.dblClick(screen.getByRole("button", { name: "Guardar alias Leche" }));
  expect(api.updateAlexaAlias).toHaveBeenCalledExactlyOnceWith(aliases[0], "Leche normal", 8);
  expect(input).toHaveProperty("disabled", true);
  await act(async () => pending.reject(new Error("La asociación ha cambiado")));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "La asociación ha cambiado");
  expect(input).toHaveProperty("value", "Leche normal");
  expect(screen.getByLabelText("Producto para Leche")).toHaveProperty("value", "8");
  await userEvent.click(screen.getByRole("button", { name: "Descartar cambios de Leche" }));
  expect(input).toHaveProperty("value", "Leche");
  expect(screen.queryByRole("alert")).toBeNull();
});
it("adds a new alias with both fields, keeps errors and locks writes during save", async () => {
  const pending = deferred<unknown>(); vi.mocked(api.saveAlexaAlias).mockReturnValue(pending.promise);
  renderWithClient(<AlexaAliases />);
  await screen.findByRole("table");
  await userEvent.selectOptions(screen.getByLabelText("Nuevo alias"), "__write_alias__");
  await userEvent.type(screen.getByLabelText("Escribir nuevo alias"), "Leche normal");
  await waitFor(() => expect(screen.getByLabelText("Producto del nuevo alias")).not.toHaveProperty("disabled", true));
  await userEvent.selectOptions(screen.getByLabelText("Producto del nuevo alias"), "7");
  await userEvent.dblClick(screen.getByRole("button", { name: "Añadir alias" }));
  expect(api.saveAlexaAlias).toHaveBeenCalledExactlyOnceWith("Leche normal", 7);
  expect(screen.getByLabelText("Producto del nuevo alias")).toHaveProperty("disabled", true);
  await act(async () => pending.reject(new Error("El alias pertenece a otro producto")));
  await screen.findByRole("alert");
  expect(screen.getByLabelText("Escribir nuevo alias")).toHaveProperty("value", "Leche normal");
});
it("keeps unavailable-product aliases visible for guarded removal or reassignment", async () => {
  vi.mocked(api.getAlexaAliases).mockResolvedValue({ aliases: [{ key: "antiguo", name: "Antiguo", product_id: 99 }] });
  vi.mocked(api.deleteAlexaAlias).mockResolvedValue({});
  renderWithClient(<AlexaAliases />);
  expect(await screen.findByText("Producto no disponible")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Guardar alias Antiguo" })).toHaveProperty("disabled", true);
  await userEvent.click(screen.getByRole("button", { name: "Eliminar alias Antiguo" }));
  expect(api.deleteAlexaAlias).toHaveBeenCalledExactlyOnceWith("antiguo", 99);
});
it("distinguishes an empty catalog of aliases, no matches and read failure", async () => {
  renderWithClient(<AlexaAliases />);
  await screen.findByRole("table");
  await userEvent.type(screen.getByRole("searchbox", { name: "Buscar alias o producto" }), "inexistente");
  expect(screen.getByText("No hay alias ni productos que coincidan con la búsqueda.")).toBeTruthy();
  expect(screen.getByLabelText("Nuevo alias")).toBeTruthy();
});

it("shows every known pending name as its own editable row before assigning a product", async () => {
  vi.mocked(api.saveAlexaAlias).mockImplementation(async () => {
    vi.mocked(api.getAlexaAliases).mockResolvedValue({ aliases: [...aliases, { key: "pan", name: "Pan", product_id: 7 }], suggestions: ["Pan", "Leche normal"] });
    return {};
  });
  renderWithClient(<AlexaAliases />);
  expect(await screen.findByLabelText("Alias: Pan")).toBeTruthy();
  expect(screen.getByLabelText("Producto para Pan")).toHaveProperty("value", "0");
  await userEvent.selectOptions(screen.getByLabelText("Producto para Pan"), "7");
  await userEvent.click(screen.getByRole("button", { name: "Guardar alias Pan" }));
  await waitFor(() => expect(screen.getByLabelText("Producto para Pan")).toHaveProperty("value", "7"));
  expect(api.saveAlexaAlias).toHaveBeenCalledExactlyOnceWith("Pan", 7);
  expect(screen.getAllByLabelText("Alias: Pan")).toHaveLength(1);
});
it("a renamed row replaces the older alias and clears the superseded row draft", async () => {
  vi.mocked(api.updateAlexaAlias).mockImplementation(async () => {
    vi.mocked(api.getAlexaAliases).mockResolvedValue({ aliases: aliases.slice(0, 2) });
    return { alias: aliases[0] };
  });
  renderWithClient(<AlexaAliases />);
  await screen.findByLabelText("Alias: Leche");
  await userEvent.selectOptions(screen.getByLabelText("Producto para Leche"), "8");
  await userEvent.selectOptions(screen.getByLabelText("Alias: Rojo"), "Leche");
  await userEvent.selectOptions(screen.getByLabelText("Producto para Rojo"), "7");
  await userEvent.click(screen.getByRole("button", { name: "Guardar alias Rojo" }));
  await waitFor(() => expect(screen.queryByLabelText("Alias: Rojo")).toBeNull());
  expect(api.updateAlexaAlias).toHaveBeenCalledExactlyOnceWith(aliases[2], "Leche", 7);
  expect(screen.getAllByLabelText("Alias: Leche")).toHaveLength(1);
  expect(screen.getByLabelText("Producto para Leche")).toHaveProperty("value", "7");
});
