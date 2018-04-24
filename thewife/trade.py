import ccxt
import attr

from logzero import logger
from time import sleep
from tenacity import retry, wait_fixed


@attr.s
class Trade:
    exchange = attr.ib()
    apikey = attr.ib()
    apisec = attr.ib()
    pair = attr.ib()
    funds = attr.ib()
    refreshrate = attr.ib()

    @property
    @retry(wait=wait_fixed(5))
    def __price(self):
        price = getattr(ccxt, self.exchange)().fetch_ticker(self.pair)['last']
        return price

    def buy(self):
        try:
            auth = getattr(ccxt, self.exchange)()
            auth.apiKey = self.apikey
            auth.secret = self.apisec

            market = auth.load_markets()
            market = market[self.pair]
            target = self.pair.split('/')[0]
            base = self.pair.split('/')[1]
            price = self.__price

            def amount(x):
                if x <= 0:
                    bal = auth.fetch_free_balance()
                    x = bal[base]

                amount_target = x / price
                amount_target = auth.amount_to_precision(
                    self.pair, amount_target)

                return amount_target

            try:
                logger.info('Attempt to buy ' + target + ' @ ' +
                            '{0:.8f}'.format(price) + ' ' + base)

                left = self.funds
                order = auth.create_limit_buy_order(self.pair,
                                                    amount(self.funds), price)

                sleep(self.refreshrate)

                while True:
                    logger.info('Check buy order status')
                    order_status = auth.fetch_order(
                        id=order['id'], symbol=order['symbol'])

                    remaining = order_status['remaining']
                    left = abs(left - order_status['cost'])
                    logger.info('Remaining: ' + str(remaining))

                    if (remaining != 0.0 or remaining != 0):
                        logger.info('Buy order was partially filled')
                        logger.info('Cancel previous buy order')

                        auth.cancel_order(
                            id=order_status['id'],
                            symbol=order_status['symbol'])

                        price = self.__price

                        logger.info('Attempt to buy ' + target + ' @ ' +
                                    '{0:.8f}'.format(price) + ' ' + base)
                        order = auth.create_limit_buy_order(
                            order_status['symbol'], amount(left), price)
                    elif (remaining == 0.0 or remaining == 0):
                        logger.info('Successfully bought ' + target)
                        break

                    sleep(self.refreshrate)
            except (ccxt.InvalidOrder, ccxt.InsufficientFunds):
                logger.info('Invalid order or quantity')
                logger.info('Funds: ' + str(self.funds))
                logger.info('Amount: ' + str(amount(self.funds)))
        except Exception as e:
            logger.exception(e)

    def sell(self):
        try:
            auth = getattr(ccxt, self.exchange)()
            auth.apiKey = self.apikey
            auth.secret = self.apisec

            market = auth.load_markets()
            market = market[self.pair]
            target = self.pair.split('/')[0]
            base = self.pair.split('/')[1]
            price = self.__price

            def balance():
                bal = auth.fetch_free_balance()
                return auth.amount_to_precision(self.pair, bal[target])

            try:
                logger.info('Attempt to sell ' + target + ' @ ' +
                            '{0:.8f}'.format(price) + ' ' + base)
                order = auth.create_limit_sell_order(self.pair, balance(),
                                                     price)

                sleep(self.refreshrate)

                while True:
                    logger.info('Check sell order status')
                    order_id = order['info']['orderId']
                    order_status = auth.fetch_order(
                        id=order_id, symbol=self.pair)

                    remaining = order_status['remaining']
                    logger.info('Remaining: ' + str(remaining))

                    if remaining != 0.0 or remaining != 0:
                        logger.info('Sell order was partially filled')
                        logger.info('Cancel previous sell order')
                        auth.cancel_order(id=order_id, symbol=self.pair)

                        price = self.__price

                        logger.info('Attempt to sell ' + target + ' @ ' +
                                    '{0:.8f}'.format(price) + ' ' + base)
                        order = auth.create_limit_sell_order(
                            self.pair, balance(), price)
                    elif remaining == 0.0 or remaining == 0:
                        logger.info('Successfully sold ' + target)
                        break

                    sleep(self.refreshrate)
            except (ccxt.InvalidOrder, ccxt.InsufficientFunds):
                logger.info('Invalid order or quantity')
                logger.info('Balance: ' + str(balance()))
        except Exception as e:
            logger.exception(e)
