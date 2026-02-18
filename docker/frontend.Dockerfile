# Multi-stage Dockerfile for Next.js frontend (ARM64 compatible)

# --- Stage 1: Dependencies ---
FROM node:20-alpine AS deps

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --ignore-scripts 2>/dev/null || npm install --ignore-scripts

# --- Stage 2: Build ---
FROM node:20-alpine AS builder

WORKDIR /app

# Next.js inlines NEXT_PUBLIC_* env vars at build time
ARG NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY
ENV NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=$NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY

COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ .

RUN npm run build

# --- Stage 3: Runtime ---
FROM node:20-alpine AS runtime

WORKDIR /app

ENV NODE_ENV=production

# Copy standalone output
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

# Create non-root user
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs
USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
