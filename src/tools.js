import fs from "node:fs/promises";
import path from "node:path";
import { ROOT } from "./config.js";
import { addFact, removeFact } from "./memory.js";

const PROJECTS_FILE = path.join(ROOT, "config", "projects.json");

export async function loadProjects() {
  try {
    return JSON.parse(await fs.readFile(PROJECTS_FILE, "utf8"));
  } catch {
    return [];
  }
}

export async function checkProject(project) {
  if (!project.healthUrl) return { name: project.name, status: "unknown", detail: "healthUrl belum diisi" };
  const started = Date.now();
  try {
    const res = await fetch(project.healthUrl, { signal: AbortSignal.timeout(5000) });
    return {
      name: project.name,
      status: res.ok ? "up" : "down",
      detail: `HTTP ${res.status}`,
      ms: Date.now() - started,
    };
  } catch (err) {
    return { name: project.name, status: "down", detail: err.cause?.code || err.message };
  }
}

// Client tools Jarvis can call. Each has a JSON schema for the API and a
// run() that validates its (untrusted) input before doing anything.
const clientTools = [
  {
    name: "remember",
    description:
      "Simpan fakta jangka panjang tentang pemilik (preferensi, orang penting, jadwal rutin, info proyek). Satu fakta singkat per panggilan.",
    input_schema: {
      type: "object",
      properties: { fact: { type: "string", description: "Fakta yang perlu diingat, ditulis sebagai kalimat utuh." } },
      required: ["fact"],
    },
    async run(input) {
      if (typeof input.fact !== "string" || !input.fact.trim()) throw new Error("fact wajib berupa teks");
      const fact = await addFact(input.fact);
      return `Tersimpan (id ${fact.id}).`;
    },
  },
  {
    name: "forget",
    description: "Hapus satu fakta dari memori jangka panjang berdasarkan id-nya.",
    input_schema: {
      type: "object",
      properties: { id: { type: "string" } },
      required: ["id"],
    },
    async run(input) {
      if (typeof input.id !== "string") throw new Error("id wajib berupa teks");
      return (await removeFact(input.id)) ? "Sudah dihapus." : "Id tidak ditemukan.";
    },
  },
  {
    name: "get_time",
    description: "Tanggal dan jam sekarang (zona waktu Asia/Jakarta).",
    input_schema: { type: "object", properties: {} },
    async run() {
      return new Date().toLocaleString("id-ID", { timeZone: "Asia/Jakarta", dateStyle: "full", timeStyle: "short" });
    },
  },
  {
    name: "list_projects",
    description: "Daftar proyek milik pemilik yang terhubung ke Jarvis (nama, deskripsi, repo, url).",
    input_schema: { type: "object", properties: {} },
    async run() {
      return JSON.stringify(await loadProjects());
    },
  },
  {
    name: "check_project",
    description: "Cek apakah sebuah proyek sedang online lewat health URL-nya.",
    input_schema: {
      type: "object",
      properties: { name: { type: "string", description: "Nama proyek persis seperti di list_projects" } },
      required: ["name"],
    },
    async run(input) {
      if (typeof input.name !== "string") throw new Error("name wajib berupa teks");
      const projects = await loadProjects();
      const project = projects.find((p) => p.name.toLowerCase() === input.name.toLowerCase());
      if (!project) return `Proyek "${input.name}" tidak ada di daftar.`;
      return JSON.stringify(await checkProject(project));
    },
  },
];

export const toolDefinitions = [
  ...clientTools.map(({ name, description, input_schema }) => ({
    name,
    description,
    input_schema,
    eager_input_streaming: true,
  })),
  { type: "web_search_20260209", name: "web_search", max_uses: 3 },
];

export async function runTool(name, input) {
  const tool = clientTools.find((t) => t.name === name);
  if (!tool) return { content: `Alat "${name}" tidak dikenal.`, is_error: true };
  if (!input || typeof input !== "object") return { content: "Input alat tidak valid.", is_error: true };
  try {
    return { content: await tool.run(input) };
  } catch (err) {
    return { content: `Gagal: ${err.message}`, is_error: true };
  }
}
