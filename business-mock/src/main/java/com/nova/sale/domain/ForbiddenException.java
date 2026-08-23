package com.nova.sale.domain;

/** 越权访问（403）：客户归属校验等硬规则拒绝。 */
public class ForbiddenException extends RuntimeException {
    public ForbiddenException(String message) {
        super(message);
    }
}
