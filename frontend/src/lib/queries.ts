import { useQuery } from "@tanstack/react-query";
import { get } from "./api";
import type { Assignment, Page, Parent, Period, SchoolClass, Section, Student, Subject, Teacher } from "./types";

export const useClasses = () => useQuery({ queryKey: ["classes"], queryFn: () => get<SchoolClass[]>("/classes") });
export const useSections = () => useQuery({ queryKey: ["sections"], queryFn: () => get<Section[]>("/sections") });
export const useSubjects = () => useQuery({ queryKey: ["subjects"], queryFn: () => get<Subject[]>("/subjects") });
export const useAssignments = (enabled = true) =>
  useQuery({ queryKey: ["assignments"], queryFn: () => get<Assignment[]>("/assignments"), enabled });
export const useAllTeachers = (enabled = true) =>
  useQuery({ queryKey: ["teachers", "all"], queryFn: () => get<Page<Teacher>>("/teachers?limit=200"), enabled });
export const useStudentPage = (params: Record<string, string | number | undefined>) => {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== "").map(([k, v]) => [k, String(v)])).toString();
  return useQuery({ queryKey: ["students", qs], queryFn: () => get<Page<Student>>(`/students?${qs}`), placeholderData: (p) => p });
};
export const useParentPage = (limit = 200) =>
  useQuery({ queryKey: ["parents", limit], queryFn: () => get<Page<Parent>>(`/parents?limit=${limit}`) });
export const useMyChildren = () => useQuery({ queryKey: ["my-children"], queryFn: () => get<Student[]>("/me/children") });

export const usePeriods = () => useQuery({ queryKey: ["periods"], queryFn: () => get<Period[]>("/periods") });

export const className = (classes: SchoolClass[] | undefined, id: number) => classes?.find((c) => c.id === id)?.name ?? "—";
export const sectionLabel = (secs: Section[] | undefined, classes: SchoolClass[] | undefined, id: number) => {
  const s = secs?.find((x) => x.id === id);
  return s ? `${className(classes, s.class_id)}-${s.name}` : "—";
};

export const subjectName = (subs: Subject[] | undefined, id: number | null) => subs?.find((s) => s.id === id)?.name ?? "—";
export const todayISO = () => new Date().toLocaleDateString("en-CA"); // yyyy-mm-dd in local time
