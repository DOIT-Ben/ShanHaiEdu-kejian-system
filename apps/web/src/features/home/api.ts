import { useQuery } from "@tanstack/react-query";
import { client, unwrap, qk } from "@/shared/api";

export function useHomeOverview() {
  return useQuery({
    queryKey: qk.home,
    queryFn: async () => {
      const result = unwrap(await client.GET("/home/overview"));
      return result.data;
    },
  });
}
