import React, { createContext, useContext } from 'react';
import { useCluster, ClusterNode } from './useCluster';

interface ClusterContextValue {
  nodes: ClusterNode[];
  loading: boolean;
  error: string | null;
  refreshCluster: () => void;
}

const ClusterCtx = createContext<ClusterContextValue>({
  nodes: [],
  loading: true,
  error: null,
  refreshCluster: () => {},
});

export function ClusterProvider({ children }: { children: React.ReactNode }) {
  const cluster = useCluster();
  return <ClusterCtx.Provider value={cluster}>{children}</ClusterCtx.Provider>;
}

export function useClusterContext(): ClusterContextValue {
  return useContext(ClusterCtx);
}
