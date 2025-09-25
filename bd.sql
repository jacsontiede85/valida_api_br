CREATE DATABASE  IF NOT EXISTS `valida_saas` /*!40100 DEFAULT CHARACTER SET latin1 COLLATE latin1_swedish_ci */;
USE `valida_saas`;
-- MySQL dump 10.13  Distrib 8.0.34, for Win64 (x86_64)
--
-- Host: 127.0.0.1    Database: valida_saas
-- ------------------------------------------------------
-- Server version	5.5.5-10.9.7-MariaDB

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Temporary view structure for view `active_subscriptions`
--

DROP TABLE IF EXISTS `active_subscriptions`;
/*!50001 DROP VIEW IF EXISTS `active_subscriptions`*/;
SET @saved_cs_client     = @@character_set_client;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50001 CREATE VIEW `active_subscriptions` AS SELECT 
 1 AS `id`,
 1 AS `user_id`,
 1 AS `plan_id`,
 1 AS `status`,
 1 AS `stripe_subscription_id`,
 1 AS `stripe_price_id`,
 1 AS `cancel_at_period_end`,
 1 AS `current_period_start`,
 1 AS `current_period_end`,
 1 AS `created_at`,
 1 AS `updated_at`,
 1 AS `email`,
 1 AS `user_name`,
 1 AS `plan_name`,
 1 AS `plan_code`,
 1 AS `price_cents`,
 1 AS `credits_included_cents`,
 1 AS `queries_limit`,
 1 AS `api_keys_limit`,
 1 AS `stripe_product_id`,
 1 AS `plan_stripe_price_id`*/;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `api_keys`
--

DROP TABLE IF EXISTS `api_keys`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `api_keys` (
  `id` char(36) NOT NULL DEFAULT uuid(),
  `user_id` char(36) NOT NULL,
  `name` varchar(100) NOT NULL,
  `description` text DEFAULT NULL,
  `key_visible` varchar(255) DEFAULT NULL COMMENT 'Chave visível (rcp_...) - NULL após primeira visualização',
  `key_hash` varchar(255) NOT NULL COMMENT 'Hash SHA256 da chave rcp_...',
  `is_active` tinyint(1) DEFAULT 1,
  `last_used_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_key_hash` (`key_hash`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_active` (`is_active`),
  KEY `idx_last_used` (`last_used_at`),
  CONSTRAINT `fk_api_keys_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Chaves de API dos usuários para integração externa';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `consultation_details`
--

DROP TABLE IF EXISTS `consultation_details`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `consultation_details` (
  `id` char(36) NOT NULL DEFAULT uuid(),
  `consultation_id` char(36) NOT NULL,
  `consultation_type_id` char(36) NOT NULL,
  `cost_cents` int(11) NOT NULL,
  `status` varchar(20) DEFAULT 'success',
  `response_data` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL COMMENT 'Dados da resposta (se necessário)' CHECK (json_valid(`response_data`)),
  `error_message` text DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_consultation_id` (`consultation_id`),
  KEY `idx_type_id` (`consultation_type_id`),
  KEY `idx_status` (`status`),
  CONSTRAINT `fk_consultation_details_consultation` FOREIGN KEY (`consultation_id`) REFERENCES `consultations` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_consultation_details_type` FOREIGN KEY (`consultation_type_id`) REFERENCES `consultation_types` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Detalhes específicos de cada tipo de consulta realizada';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `consultation_types`
--

DROP TABLE IF EXISTS `consultation_types`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `consultation_types` (
  `id` char(36) NOT NULL DEFAULT uuid(),
  `code` varchar(50) NOT NULL COMMENT 'Código único (protestos, receita_federal, etc)',
  `name` varchar(100) NOT NULL,
  `description` text DEFAULT NULL,
  `cost_cents` int(11) NOT NULL COMMENT 'Custo por consulta em centavos',
  `provider` varchar(100) DEFAULT NULL COMMENT 'Provedor do serviço (resolve_cenprot, cnpja, etc)',
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_code` (`code`),
  KEY `idx_active` (`is_active`),
  KEY `idx_cost` (`cost_cents`),
  KEY `idx_provider` (`provider`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Tipos de consulta disponíveis e seus custos';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `consultations`
--

DROP TABLE IF EXISTS `consultations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `consultations` (
  `id` char(36) NOT NULL DEFAULT uuid(),
  `user_id` char(36) NOT NULL,
  `api_key_id` char(36) DEFAULT NULL,
  `cnpj` varchar(18) NOT NULL,
  `status` varchar(20) DEFAULT 'success',
  `total_cost_cents` int(11) NOT NULL DEFAULT 0,
  `response_time_ms` int(11) DEFAULT NULL,
  `error_message` text DEFAULT NULL,
  `cache_used` tinyint(1) DEFAULT 0,
  `client_ip` varchar(45) DEFAULT NULL COMMENT 'IP do cliente (IPv4 ou IPv6)',
  `created_at` datetime DEFAULT current_timestamp(),
  `response_data` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL COMMENT 'JSON completo retornado pela rota /api/v1/cnpj/consult' CHECK (json_valid(`response_data`)),
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_api_key_id` (`api_key_id`),
  KEY `idx_cnpj` (`cnpj`),
  KEY `idx_status` (`status`),
  KEY `idx_created_at` (`created_at`),
  KEY `idx_user_created` (`user_id`,`created_at`),
  KEY `idx_consultations_user_date` (`user_id`,`created_at`),
  KEY `idx_consultations_status_date` (`status`,`created_at`),
  KEY `idx_consultations_cnpj_user` (`cnpj`,`user_id`),
  CONSTRAINT `fk_consultations_api_key` FOREIGN KEY (`api_key_id`) REFERENCES `api_keys` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_consultations_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Histórico de consultas realizadas pelos usuários';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `credit_transactions`
--

DROP TABLE IF EXISTS `credit_transactions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `credit_transactions` (
  `id` char(36) NOT NULL DEFAULT uuid(),
  `user_id` char(36) NOT NULL,
  `consultation_id` char(36) DEFAULT NULL,
  `type` varchar(20) NOT NULL COMMENT 'add, subtract, purchase, spend',
  `amount_cents` int(11) NOT NULL COMMENT 'Valor da transação em centavos',
  `balance_after_cents` int(11) NOT NULL COMMENT 'Saldo após a transação em centavos',
  `description` text NOT NULL,
  `stripe_payment_intent_id` varchar(255) DEFAULT NULL,
  `stripe_invoice_id` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_consultation_id` (`consultation_id`),
  KEY `idx_type` (`type`),
  KEY `idx_created_at` (`created_at`),
  KEY `idx_user_created` (`user_id`,`created_at`),
  KEY `idx_credit_transactions_user_balance` (`user_id`,`balance_after_cents`),
  CONSTRAINT `fk_credit_transactions_consultation` FOREIGN KEY (`consultation_id`) REFERENCES `consultations` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_credit_transactions_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Histórico completo de transações de crédito';
/*!40101 SET character_set_client = @saved_cs_client */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_AUTO_CREATE_USER,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`%`*/ /*!50003 TRIGGER trigger_update_user_credits_simplified
        BEFORE INSERT ON credit_transactions
        FOR EACH ROW
        BEGIN
            DECLARE current_balance INT DEFAULT 0;
            
            SELECT COALESCE(SUM(
                CASE 
                    WHEN type IN ('add', 'purchase') THEN amount_cents
                    WHEN type IN ('subtract', 'spend', 'usage') THEN amount_cents
                    ELSE 0
                END
            ), 0) INTO current_balance
            FROM credit_transactions 
            WHERE user_id = NEW.user_id;
            
            SET current_balance = current_balance + NEW.amount_cents;
            SET NEW.balance_after_cents = current_balance;
            
            UPDATE users 
            SET credits = current_balance / 100.0
            WHERE id = NEW.user_id;
        END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;

--
-- Table structure for table `stripe_webhook_logs`
--

DROP TABLE IF EXISTS `stripe_webhook_logs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `stripe_webhook_logs` (
  `id` char(36) NOT NULL DEFAULT uuid(),
  `event_id` varchar(255) NOT NULL,
  `event_type` varchar(100) NOT NULL,
  `processed` tinyint(1) DEFAULT 0,
  `error_message` text DEFAULT NULL,
  `webhook_data` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`webhook_data`)),
  `created_at` datetime DEFAULT current_timestamp(),
  `processed_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_event_id` (`event_id`),
  KEY `idx_event_type` (`event_type`),
  KEY `idx_processed` (`processed`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Log de eventos recebidos via webhooks do Stripe';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `subscription_plans`
--

DROP TABLE IF EXISTS `subscription_plans`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `subscription_plans` (
  `id` char(36) NOT NULL DEFAULT uuid(),
  `user_id` char(36) DEFAULT NULL,
  `code` varchar(50) NOT NULL COMMENT 'Código único do plano (starter, pro, enterprise)',
  `name` varchar(100) NOT NULL,
  `description` text DEFAULT NULL,
  `price_cents` int(11) NOT NULL COMMENT 'Preço em centavos (ex: 2990 = R$ 29,90)',
  `credits_included_cents` int(11) NOT NULL DEFAULT 0 COMMENT 'Créditos inclusos em centavos',
  `api_keys_limit` int(11) DEFAULT 1,
  `queries_limit` int(11) DEFAULT NULL COMMENT 'Limite de consultas por mês (NULL = ilimitado)',
  `is_active` tinyint(1) DEFAULT 1,
  `stripe_product_id` varchar(255) DEFAULT NULL,
  `stripe_price_id` varchar(255) DEFAULT NULL,
  `features` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL COMMENT 'Recursos específicos do plano' CHECK (json_valid(`features`)),
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_code` (`code`),
  KEY `idx_active` (`is_active`),
  KEY `idx_price_cents` (`price_cents`),
  KEY `idx_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Planos de assinatura disponíveis no sistema';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `subscriptions`
--

DROP TABLE IF EXISTS `subscriptions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `subscriptions` (
  `id` char(36) NOT NULL DEFAULT uuid(),
  `user_id` char(36) NOT NULL,
  `plan_id` char(36) NOT NULL,
  `status` varchar(50) DEFAULT 'active',
  `stripe_subscription_id` varchar(255) DEFAULT NULL,
  `stripe_price_id` varchar(255) DEFAULT NULL,
  `cancel_at_period_end` tinyint(1) DEFAULT 0,
  `current_period_start` datetime DEFAULT NULL,
  `current_period_end` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_plan_id` (`plan_id`),
  KEY `idx_status` (`status`),
  KEY `idx_period_end` (`current_period_end`),
  CONSTRAINT `fk_subscriptions_plan` FOREIGN KEY (`plan_id`) REFERENCES `subscription_plans` (`id`),
  CONSTRAINT `fk_subscriptions_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Assinaturas ativas dos usuários';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Temporary view structure for view `user_credits_summary`
--

DROP TABLE IF EXISTS `user_credits_summary`;
/*!50001 DROP VIEW IF EXISTS `user_credits_summary`*/;
SET @saved_cs_client     = @@character_set_client;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50001 CREATE VIEW `user_credits_summary` AS SELECT 
 1 AS `id`,
 1 AS `email`,
 1 AS `name`,
 1 AS `current_credits`,
 1 AS `total_purchased`,
 1 AS `total_spent`,
 1 AS `transaction_count`,
 1 AS `user_created_at`,
 1 AS `last_transaction`*/;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` char(36) NOT NULL DEFAULT uuid(),
  `email` varchar(255) NOT NULL,
  `name` varchar(255) NOT NULL,
  `password_hash` varchar(255) DEFAULT NULL,
  `last_login` datetime DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT 1,
  `stripe_customer_id` varchar(255) DEFAULT NULL COMMENT 'ID do cliente no Stripe',
  `credits` decimal(10,2) DEFAULT 0.00 COMMENT 'Saldo atual de créditos em reais',
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_email` (`email`),
  KEY `idx_stripe_customer` (`stripe_customer_id`),
  KEY `idx_email` (`email`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Tabela principal de usuários do sistema SaaS';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping events for database 'valida_saas'
--

--
-- Dumping routines for database 'valida_saas'
--

--
-- Final view structure for view `active_subscriptions`
--

/*!50001 DROP VIEW IF EXISTS `active_subscriptions`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_general_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `active_subscriptions` AS select `s`.`id` AS `id`,`s`.`user_id` AS `user_id`,`s`.`plan_id` AS `plan_id`,`s`.`status` AS `status`,`s`.`stripe_subscription_id` AS `stripe_subscription_id`,`s`.`stripe_price_id` AS `stripe_price_id`,`s`.`cancel_at_period_end` AS `cancel_at_period_end`,`s`.`current_period_start` AS `current_period_start`,`s`.`current_period_end` AS `current_period_end`,`s`.`created_at` AS `created_at`,`s`.`updated_at` AS `updated_at`,`u`.`email` AS `email`,`u`.`name` AS `user_name`,`sp`.`name` AS `plan_name`,`sp`.`code` AS `plan_code`,`sp`.`price_cents` AS `price_cents`,`sp`.`credits_included_cents` AS `credits_included_cents`,`sp`.`queries_limit` AS `queries_limit`,`sp`.`api_keys_limit` AS `api_keys_limit`,`sp`.`stripe_product_id` AS `stripe_product_id`,`sp`.`stripe_price_id` AS `plan_stripe_price_id` from ((`subscriptions` `s` join `users` `u` on(`s`.`user_id` = `u`.`id`)) join `subscription_plans` `sp` on(`s`.`plan_id` = `sp`.`id`)) where `s`.`status` = 'active' */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;

--
-- Final view structure for view `user_credits_summary`
--

/*!50001 DROP VIEW IF EXISTS `user_credits_summary`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_general_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `user_credits_summary` AS select `u`.`id` AS `id`,`u`.`email` AS `email`,`u`.`name` AS `name`,`u`.`credits` AS `current_credits`,coalesce(`ct`.`total_purchased`,0) AS `total_purchased`,coalesce(`ct`.`total_spent`,0) AS `total_spent`,coalesce(`ct`.`transaction_count`,0) AS `transaction_count`,`u`.`created_at` AS `user_created_at`,coalesce(`ct`.`last_transaction`,`u`.`created_at`) AS `last_transaction` from (`users` `u` left join (select `credit_transactions`.`user_id` AS `user_id`,sum(case when `credit_transactions`.`type` in ('add','purchase') then `credit_transactions`.`amount_cents` else 0 end) / 100.0 AS `total_purchased`,sum(case when `credit_transactions`.`type` in ('subtract','spend') then `credit_transactions`.`amount_cents` else 0 end) / 100.0 AS `total_spent`,count(0) AS `transaction_count`,max(`credit_transactions`.`created_at`) AS `last_transaction` from `credit_transactions` group by `credit_transactions`.`user_id`) `ct` on(`u`.`id` = `ct`.`user_id`)) */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-09-25 10:45:15
