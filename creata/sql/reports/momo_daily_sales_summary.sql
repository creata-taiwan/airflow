-- Licensed to the Apache Software Foundation (ASF) under one
-- or more contributor license agreements. See the NOTICE file
-- distributed with Apache Airflow for additional information
-- regarding copyright ownership. The ASF licenses this file to you under
-- the Apache License, Version 2.0.

SELECT
    N'{source_database}' AS source_database,
    CAST(PR.BillDate AS int) AS report_date_int,
    SUM(CASE WHEN PR.Flag = 500 THEN PR.Amount ELSE 0 END) AS gross_sales_amount,
    SUM(CASE WHEN PR.Flag = 600 THEN PR.Amount ELSE 0 END) AS return_amount,
    SUM(CASE WHEN PR.Flag = 500 THEN PR.Amount
             WHEN PR.Flag = 600 THEN -PR.Amount
             ELSE 0 END) AS net_sales_amount,
    SUM(CASE WHEN PR.Flag = 500 THEN PR.Quantity
             WHEN PR.Flag = 600 THEN -PR.Quantity
             ELSE 0 END) AS net_quantity,
    COUNT(DISTINCT CASE WHEN PR.Flag = 500 THEN BA.FundBillNo ELSE NULL END) AS order_count
FROM {database}.dbo.comBillAccounts BA
JOIN {database}.dbo.comProdRec PR
    ON BA.FundBillNo = PR.BillNO
   AND BA.Flag = PR.Flag
LEFT JOIN {database}.dbo.comCustomer CU
    ON CU.ID = BA.DueTo
WHERE PR.Flag IN (500, 600)
  AND PR.BillDate = ?
  AND PR.ProdID NOT LIKE '#%'
  AND {channel_field} LIKE ?
GROUP BY CAST(PR.BillDate AS int);
