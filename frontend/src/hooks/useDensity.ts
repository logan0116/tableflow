import { useCallback, useState } from "react";

import { readDensity, writeDensity, type Density } from "../ui-prefs";

/** 行密度：默认舒适档，选择结果持久化到 localStorage。 */
export function useDensity(): [Density, (density: Density) => void] {
  const [density, setDensityState] = useState<Density>(() => readDensity());

  const setDensity = useCallback((next: Density) => {
    const value: Density = next === "compact" ? "compact" : "comfortable";
    setDensityState(value);
    writeDensity(value);
  }, []);

  return [density, setDensity];
}
