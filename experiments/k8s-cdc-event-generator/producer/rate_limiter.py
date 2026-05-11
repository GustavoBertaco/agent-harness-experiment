import time


class RateLimiter:
    def __init__(self, rate: float):
        self.rate = rate
        self.capacity = float(rate)  # 1-second burst cap
        self.tokens = float(rate)    # start full
        self.last_refill = time.time()

    def acquire(self) -> None:
        now = time.time()
        elapsed = now - self.last_refill
        self.last_refill = now

        self.tokens += elapsed * self.rate
        if self.tokens > self.capacity:
            self.tokens = self.capacity

        if self.tokens < 1.0:
            deficit = 1.0 - self.tokens
            time.sleep(deficit / self.rate)
            self.last_refill = time.time()  # restart refill window post-sleep
            self.tokens = 0.0
        else:
            self.tokens -= 1.0
