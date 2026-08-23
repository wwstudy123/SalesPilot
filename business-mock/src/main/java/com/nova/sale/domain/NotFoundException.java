package com.nova.sale.domain;

/** 资源不存在（404）。 */
public class NotFoundException extends RuntimeException {
    public NotFoundException(String message) {
        super(message);
    }
}
