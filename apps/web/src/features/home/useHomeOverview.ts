import { useQuery } from "@tanstack/react-query";
import { client, qk, unwrap } from "@/shared/api";

export function useHomeOverview() {
  return useQuery({
    queryKey: qk.homeOverview,
    queryFn: async () => {
      const result = await client.GET("/home/overview", {});
      return unwrap(result).data;
    },
  });
}
