// Invalidate synchronously when an edit arrives, including the debounce window.
export function latestRequest() {
  let current: AbortController | undefined;
  function cancel() {
    current?.abort();
    current = undefined;
  }
  return {
    cancel,
    begin() {
      cancel();
      const controller = new AbortController();
      current = controller;
      return {
        signal: controller.signal,
        isCurrent: () => current === controller,
      };
    },
  };
}
