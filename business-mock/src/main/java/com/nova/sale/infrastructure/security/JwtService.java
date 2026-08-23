package com.nova.sale.infrastructure.security;

import com.nova.sale.domain.model.Employee;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.Date;
import java.util.Optional;

/** JWT 签发与校验（HS256 共享密钥，三端校验）。 */
@Component
public class JwtService {
    private final SecretKey key;
    private final Duration ttl;

    public JwtService(
            @Value("${sale.jwt.secret:sale-dev-jwt-secret-please-change-me-0123456789}") String secret,
            @Value("${sale.jwt.ttl-hours:12}") long ttlHours
    ) {
        this.key = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
        this.ttl = Duration.ofHours(ttlHours);
    }

    public String createToken(Employee employee) {
        Instant now = Instant.now();
        return Jwts.builder()
                .subject(employee.username())
                .claim("eid", employee.id())
                .claim("name", employee.name())
                .claim("role", employee.role())
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plus(ttl)))
                .signWith(key)
                .compact();
    }

    public Optional<AuthContext> parse(String token) {
        try {
            Claims claims = Jwts.parser().verifyWith(key).build()
                    .parseSignedClaims(token).getPayload();
            return Optional.of(new AuthContext(
                    claims.get("eid", Long.class),
                    claims.getSubject(),
                    claims.get("role", String.class)
            ));
        } catch (JwtException | IllegalArgumentException ex) {
            return Optional.empty();
        }
    }
}
